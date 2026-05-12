import os
import requests
import json

OPENAI_API_KEY = os.environ.get('AI_INTEGRATIONS_OPENAI_API_KEY')
OPENAI_BASE_URL = os.environ.get('AI_INTEGRATIONS_OPENAI_BASE_URL', 'https://api.openai.com/v1')

def analyze_document(text: str, title: str) -> dict:
    """Analyze document text and extract summary and keywords using AI."""
    if not text or len(text.strip()) < 50:
        return {'summary': '', 'keywords': []}
    
    if not OPENAI_API_KEY:
        return fallback_analysis(text, title)
    
    try:
        truncated_text = text[:8000] if len(text) > 8000 else text
        
        prompt = f"""Analyze this document and provide:
1. A concise summary (2-3 sentences)
2. 5-8 relevant keywords

Document Title: {title}

Document Content:
{truncated_text}

Respond in JSON format:
{{"summary": "...", "keywords": ["keyword1", "keyword2", ...]}}"""

        response = requests.post(
            f"{OPENAI_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": "You are a document analysis assistant. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 500
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            content = content.strip()
            if content.startswith('```'):
                content = content.split('\n', 1)[1] if '\n' in content else content[3:]
                if content.endswith('```'):
                    content = content[:-3]
            parsed = json.loads(content)
            return {
                'summary': parsed.get('summary', ''),
                'keywords': parsed.get('keywords', [])
            }
        else:
            print(f"AI API error: {response.status_code}")
            return fallback_analysis(text, title)
            
    except Exception as e:
        print(f"AI analysis error: {e}")
        return fallback_analysis(text, title)

def fallback_analysis(text: str, title: str) -> dict:
    """Simple keyword extraction without AI."""
    import re
    
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    word_freq = {}
    stopwords = {'this', 'that', 'with', 'from', 'have', 'been', 'were', 'they', 
                 'their', 'what', 'when', 'where', 'which', 'while', 'would', 
                 'could', 'should', 'there', 'these', 'those', 'being', 'about'}
    
    for word in words:
        if word not in stopwords:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    keywords = [word for word, _ in sorted_words[:8]]
    
    sentences = text.split('.')[:3]
    summary = '. '.join(s.strip() for s in sentences if s.strip())[:500]
    
    return {
        'summary': summary if summary else f"Document: {title}",
        'keywords': keywords
    }

def semantic_search(query: str, documents: list) -> list:
    """Perform semantic search using AI to rank documents by relevance."""
    if not documents:
        return []
    
    if not OPENAI_API_KEY:
        return [d['id'] for d in documents]
    
    try:
        doc_summaries = []
        for doc in documents[:20]:
            summary = f"ID: {doc['id']}, Title: {doc['title']}"
            if doc.get('aiSummary'):
                summary += f", Summary: {doc['aiSummary'][:200]}"
            if doc.get('aiKeywords'):
                summary += f", Keywords: {', '.join(doc['aiKeywords'][:5])}"
            doc_summaries.append(summary)
        
        prompt = f"""Given this search query: "{query}"

Rank these documents by relevance (most relevant first). Return only the document IDs in order.

Documents:
{chr(10).join(doc_summaries)}

Return a JSON array of document IDs: [id1, id2, ...]"""

        response = requests.post(
            f"{OPENAI_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": "You are a search ranking assistant. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 200
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            if content.startswith('```'):
                content = content.split('\n', 1)[1] if '\n' in content else content[3:]
                if content.endswith('```'):
                    content = content[:-3]
            ranked_ids = json.loads(content)
            return ranked_ids
        
        return [d['id'] for d in documents]
        
    except Exception as e:
        print(f"Semantic search error: {e}")
        return [d['id'] for d in documents]

class AIService:
    """AI service wrapper class for document operations."""
    
    def __init__(self):
        self.api_key = OPENAI_API_KEY
        self.base_url = OPENAI_BASE_URL
    
    def analyze_document(self, text: str, title: str) -> dict:
        return analyze_document(text, title)
    
    def semantic_search(self, query: str, documents: list) -> list:
        return semantic_search(query, documents)
    
    def chat_with_documents(self, message: str) -> str:
        """Chat about documents in the archive."""
        if not self.api_key:
            return "AI features are currently unavailable. Please check your API configuration."
        
        try:
            prompt = f"""You are Vicente, an AI document assistant for AFPMBAI (Armed Forces and Police Mutual Benefit Association Incorporated). You help users find and understand documents in the archive.

The user is asking: {message}

Provide a helpful, professional response. If the question is about specific documents, explain that you can help search for and analyze documents in the archive. Be concise but thorough."""

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": "You are Vicente, a professional AI document assistant for AFPMBAI."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 500
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                return "I apologize, but I'm having trouble processing your request. Please try again."
                
        except Exception as e:
            print(f"Chat error: {e}")
            return "I encountered an error while processing your message. Please try again."
