"""
RAG (Retrieval-Augmented Generation) service powered by Docling.

Pipeline:
  1. Document text is extracted using Docling DocumentConverter with OCR support
     - Text-layer PDFs: fast C++ parser extracts embedded text
     - Scanned PDFs / images: EasyOCR or Tesseract performs optical character recognition
  2. Text is split into semantically meaningful chunks
  3. Each chunk is embedded using OpenAI text-embedding-3-small
  4. Embeddings + chunks are stored in the document_chunks PostgreSQL table
  5. On search/chat: the query is embedded and cosine similarity ranks retrieved chunks
  6. Top-k chunks are fed to the configured LLM (default: gemma3:1b) as grounded context (RAG generation)
"""

import os
import json
import math
import requests

OPENAI_API_KEY = os.environ.get('AI_INTEGRATIONS_OPENAI_API_KEY')
OPENAI_BASE_URL = os.environ.get('AI_INTEGRATIONS_OPENAI_BASE_URL', 'https://api.openai.com/v1')

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120
EMBEDDING_MODEL = 'nomic-embed-text'
EMBED_DIMENSIONS = 1536


# ---------------------------------------------------------------------------
# Chunking helpers
# ---------------------------------------------------------------------------

def _hard_split(text: str, max_size: int, overlap: int) -> list:
    """Force-split a single oversized string into max_size pieces with overlap."""
    if len(text) <= max_size:
        return [text] if text.strip() else []
    step = max(1, max_size - overlap)
    return [text[i:i + max_size] for i in range(0, len(text), step) if text[i:i + max_size].strip()]


def _split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list:
    """
    Split text into overlapping chunks, preferring paragraph boundaries.
    Guarantees no chunk exceeds chunk_size (oversized paragraphs are hard-split).
    """
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

    chunks = []
    current = []
    current_len = 0

    for para in paragraphs:
        # If a single paragraph exceeds chunk_size, flush current then hard-split it.
        if len(para) > chunk_size:
            if current:
                chunks.append('\n\n'.join(current))
                current = []
                current_len = 0
            chunks.extend(_hard_split(para, chunk_size, overlap))
            continue

        if current_len + len(para) > chunk_size and current:
            chunk_text = '\n\n'.join(current)
            chunks.append(chunk_text)
            overlap_text = chunk_text[-overlap:] if len(chunk_text) > overlap else chunk_text
            current = [overlap_text] if overlap_text.strip() else []
            current_len = len(overlap_text)
        current.append(para)
        current_len += len(para) + 2

    if current:
        chunks.append('\n\n'.join(current))

    if not chunks and text.strip():
        chunks = _hard_split(text, chunk_size, overlap)

    # Final safety net: nothing leaves this function over chunk_size.
    safe = []
    for c in chunks:
        if not c.strip():
            continue
        if len(c) > chunk_size:
            safe.extend(_hard_split(c, chunk_size, overlap))
        else:
            safe.append(c)
    return safe


def build_chunks_from_pages(pages: list) -> list:
    """
    Build RAG chunks from Docling page data.
    pages: list of {'page': int, 'text': str}
    Returns list of {'chunk_index': int, 'page_number': int, 'chunk_text': str}
    """
    result = []
    idx = 0
    for page_data in pages:
        page_num = page_data.get('page', 0)
        page_text = page_data.get('text', '').strip()
        if not page_text:
            continue
        for chunk in _split_into_chunks(page_text):
            result.append({
                'chunk_index': idx,
                'page_number': page_num,
                'chunk_text': chunk,
            })
            idx += 1
    return result


def build_chunks_from_text(text: str) -> list:
    """
    Build RAG chunks from plain extracted text (for DOCX, TXT, and fallback).
    Returns list of {'chunk_index': int, 'page_number': None, 'chunk_text': str}
    """
    chunks = _split_into_chunks(text)
    return [
        {'chunk_index': i, 'page_number': None, 'chunk_text': c}
        for i, c in enumerate(chunks)
    ]


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

def _embed_single(text: str) -> list:
    """Embed one text string. Returns vector or None on failure."""
    try:
        response = requests.post(
            f"{OPENAI_BASE_URL}/embeddings",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={"model": EMBEDDING_MODEL, "input": [text]},
            timeout=20
        )
        if response.status_code == 200:
            return response.json()['data'][0]['embedding']
        print(f"  Embed single error {response.status_code}: {response.text[:120]}", flush=True)
        return None
    except Exception as e:
        print(f"  Embed single failed: {e}", flush=True)
        return None


def embed_texts(texts: list) -> list:
    """
    Generate embeddings for a list of text strings using the embeddings API.
    Returns list of embedding vectors, or None entries on failure.

    Strategy:
      - Truncate every input to MAX_EMBED_CHARS (safe for nomic-embed-text 2048-token window).
      - Send in small batches; on batch failure, retry each item individually so one
        bad chunk doesn't poison good neighbors.
      - Log progress per batch so the operator can see indexing isn't hung.
    """
    if not texts or not OPENAI_API_KEY:
        return [None] * len(texts)

    MAX_EMBED_CHARS = 4000   # ~1000 tokens â€” well under nomic-embed-text's 2048 limit
    BATCH_SIZE = 16          # small batches => fast per-batch round-trips
    BATCH_TIMEOUT = 30       # seconds

    embeddings = []
    total = len(texts)
    print(f"RAG: embedding {total} chunks (batch={BATCH_SIZE}, max_chars={MAX_EMBED_CHARS})...", flush=True)

    for i in range(0, total, BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        cleaned = [(t or '')[:MAX_EMBED_CHARS] for t in batch]
        batch_no = (i // BATCH_SIZE) + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        try:
            response = requests.post(
                f"{OPENAI_BASE_URL}/embeddings",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={"model": EMBEDDING_MODEL, "input": cleaned},
                timeout=BATCH_TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                batch_embeddings = [item['embedding'] for item in sorted(data['data'], key=lambda x: x['index'])]
                embeddings.extend(batch_embeddings)
                print(f"  batch {batch_no}/{total_batches} ok ({len(batch)} chunks)", flush=True)
            else:
                print(f"  batch {batch_no}/{total_batches} HTTP {response.status_code}: {response.text[:120]} â€” retrying per-item", flush=True)
                for single_text in cleaned:
                    embeddings.append(_embed_single(single_text))
        except Exception as e:
            print(f"  batch {batch_no}/{total_batches} exception: {e} â€” retrying per-item", flush=True)
            for single_text in cleaned:
                embeddings.append(_embed_single(single_text))

    ok = sum(1 for e in embeddings if e is not None)
    print(f"RAG: embeddings done â€” {ok}/{total} succeeded", flush=True)
    return embeddings


def embed_query(query: str) -> list:
    """Embed a single query string. Returns vector or None."""
    results = embed_texts([query])
    return results[0] if results else None


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------

def cosine_similarity(vec_a: list, vec_b: list) -> float:
    """Compute cosine similarity between two vectors."""
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ---------------------------------------------------------------------------
# Indexing (called on upload / reindex)
# ---------------------------------------------------------------------------

def index_document(document, file_path: str = None, file_type: str = None,
                   pre_extracted_pages: list = None):
    """
    Full RAG indexing pipeline for a document:
      1. Use pre-extracted pages (PDFs before encryption) OR fall back to stored text
      2. Build semantic chunks
      3. Generate embeddings via OpenAI
      4. Store in document_chunks table
    Must be called within an active Flask app context.

    Args:
        document: SQLAlchemy Document instance (must already have an id)
        file_path: Path to the original file (used only if pre_extracted_pages not provided)
        file_type: File extension string
        pre_extracted_pages: Pre-extracted page list from extract_pdf_text_with_pages(),
                             pass this for PDFs to avoid re-reading after encryption
    """
    from extensions import db
    from models import DocumentChunk

    try:
        print(f"RAG: indexing document {document.id} ('{document.title[:60]}')...", flush=True)
        DocumentChunk.query.filter_by(document_id=document.id).delete()
        db.session.flush()

        if pre_extracted_pages is not None:
            chunks_data = build_chunks_from_pages(pre_extracted_pages)
        elif file_path and file_type and file_type.lower() in ['pdf', 'jpg', 'jpeg', 'png']:
            from services.document_parser import extract_pdf_text_with_pages
            pages = extract_pdf_text_with_pages(file_path)
            chunks_data = build_chunks_from_pages(pages)
        else:
            text = document.extracted_text or ''
            chunks_data = build_chunks_from_text(text)

        if not chunks_data:
            print(f"RAG: no chunks produced for document {document.id}", flush=True)
            return 0

        print(f"RAG: built {len(chunks_data)} chunks for document {document.id}", flush=True)
        texts = [c['chunk_text'] for c in chunks_data]
        embeddings = embed_texts(texts)

        for chunk_data, embedding in zip(chunks_data, embeddings):
            chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=chunk_data['chunk_index'],
                chunk_text=chunk_data['chunk_text'],
                embedding=embedding,
                page_number=chunk_data.get('page_number'),
            )
            db.session.add(chunk)

        db.session.commit()
        print(f"RAG: indexed {len(chunks_data)} chunks for document {document.id}", flush=True)
        return len(chunks_data)

    except Exception as e:
        print(f"RAG indexing error for document {document.id}: {e}", flush=True)
        db.session.rollback()
        return 0


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve_relevant_chunks(query: str, document_id: int = None, top_k: int = 5) -> list:
    """
    Retrieve the most relevant document chunks for a query.

    Strategy (in order of preference):
      1. OpenAI vector embeddings (cosine similarity) â€” when stored embeddings exist
      2. TF-IDF cosine similarity via scikit-learn â€” always available, no API needed
      3. Keyword hit-count fallback â€” last resort

    Args:
        query: Natural language question or search string
        document_id: If set, search only within that document
        top_k: Number of top chunks to return

    Returns:
        List of dicts: [{'document_id', 'document_title', 'chunk_text', 'page_number', 'score'}]
    """
    from models import DocumentChunk, Document

    q = DocumentChunk.query.join(Document)
    if document_id:
        q = q.filter(DocumentChunk.document_id == document_id)
    chunks = q.all()

    if not chunks:
        return []

    chunks_with_embeddings = [c for c in chunks if c.embedding]
    if chunks_with_embeddings:
        query_vec = embed_query(query)
        if query_vec is not None:
            scored = []
            for chunk in chunks_with_embeddings:
                score = cosine_similarity(query_vec, chunk.embedding)
                scored.append({
                    'document_id': chunk.document_id,
                    'document_title': chunk.document.title if chunk.document else '',
                    'chunk_text': chunk.chunk_text,
                    'page_number': chunk.page_number,
                    'score': score,
                })
            scored.sort(key=lambda x: x['score'], reverse=True)
            scored = [s for s in scored if s['score'] >= 0.25]
            return scored[:top_k]

    return _tfidf_retrieval(query, document_id, top_k)


def _tfidf_retrieval(query: str, document_id: int, top_k: int) -> list:
    """
    TF-IDF based chunk retrieval â€” used when vector embeddings are unavailable.
    Uses scikit-learn TfidfVectorizer for cosine similarity ranking.
    """
    from models import DocumentChunk, Document

    q = DocumentChunk.query.join(Document)
    if document_id:
        q = q.filter(DocumentChunk.document_id == document_id)
    chunks = q.all()

    if not chunks:
        return []

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        texts = [c.chunk_text for c in chunks]
        corpus = [query] + texts

        vectorizer = TfidfVectorizer(
            stop_words='english',
            ngram_range=(1, 2),
            max_features=10000,
            sublinear_tf=True
        )
        tfidf_matrix = vectorizer.fit_transform(corpus)
        query_vec = tfidf_matrix[0:1]
        chunk_vecs = tfidf_matrix[1:]
        scores = cosine_similarity(query_vec, chunk_vecs).flatten()

        results = []
        for chunk, score in zip(chunks, scores):
            if score >= 0.1:
                results.append({
                    'document_id': chunk.document_id,
                    'document_title': chunk.document.title if chunk.document else '',
                    'chunk_text': chunk.chunk_text,
                    'page_number': chunk.page_number,
                    'score': float(score),
                })

        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]

    except Exception as e:
        print(f"TF-IDF retrieval failed, using keyword fallback: {e}")
        return _keyword_fallback(query, chunks, top_k)


def _keyword_fallback(query: str, chunks: list, top_k: int) -> list:
    """Last-resort keyword match when both vector and TF-IDF retrieval fail."""
    import re
    words = set(re.findall(r'\b\w{4,}\b', query.lower()))
    results = []
    for chunk in chunks:
        text_lower = chunk.chunk_text.lower()
        hits = sum(1 for w in words if w in text_lower)
        if hits:
            results.append({
                'document_id': chunk.document_id,
                'document_title': chunk.document.title if chunk.document else '',
                'chunk_text': chunk.chunk_text,
                'page_number': chunk.page_number,
                'score': hits / max(len(words), 1),
            })
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_k]


def build_rag_context(chunks: list, max_chars: int = 6000) -> str:
    """
    Format retrieved chunks into a context string for the LLM.
    """
    if not chunks:
        return ""

    parts = []
    total = 0
    seen_docs = {}

    for chunk in chunks:
        doc_title = chunk.get('document_title', 'Unknown')
        page = chunk.get('page_number')
        text = chunk.get('chunk_text', '')
        source = f"[{doc_title}" + (f", page {page}" if page else "") + "]"

        entry = f"{source}\n{text}"
        if total + len(entry) > max_chars:
            break
        parts.append(entry)
        total += len(entry)
        seen_docs[doc_title] = True

    return '\n\n---\n\n'.join(parts)
