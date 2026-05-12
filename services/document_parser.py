import os

def extract_text_from_file(file_path: str, file_type: str) -> str:
    """Extract text content from various file types using pymupdf4llm."""
    try:
        if file_type.lower() == 'pdf':
            return extract_pdf_text(file_path)
        elif file_type.lower() in ['doc', 'docx']:
            return extract_docx_text(file_path)
        elif file_type.lower() == 'txt':
            return extract_txt_text(file_path)
        else:
            return ""
    except Exception as e:
        print(f"Error extracting text from {file_path}: {e}")
        return ""

def extract_pdf_text(file_path: str) -> str:
    """Extract text from PDF using pymupdf4llm."""
    try:
        import pymupdf4llm
        md_text = pymupdf4llm.to_markdown(file_path)
        return md_text
    except Exception as e:
        try:
            import fitz
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except Exception as e2:
            print(f"PDF extraction failed: {e2}")
            return ""

def extract_docx_text(file_path: str) -> str:
    """Extract text from DOCX files."""
    try:
        import zipfile
        import xml.etree.ElementTree as ET
        
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            if 'word/document.xml' in zip_ref.namelist():
                xml_content = zip_ref.read('word/document.xml')
                tree = ET.fromstring(xml_content)
                
                namespaces = {
                    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
                }
                
                text_parts = []
                for elem in tree.iter():
                    if elem.tag.endswith('}t'):
                        if elem.text:
                            text_parts.append(elem.text)
                
                return ' '.join(text_parts)
        return ""
    except Exception as e:
        print(f"DOCX extraction failed: {e}")
        return ""

def extract_txt_text(file_path: str) -> str:
    """Extract text from TXT files."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        print(f"TXT extraction failed: {e}")
        return ""
