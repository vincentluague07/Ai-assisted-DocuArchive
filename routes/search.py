from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import Document, ActivityLog
from services.ai_service import semantic_search
from sqlalchemy import or_

search_bp = Blueprint('search', __name__)

def log_activity(user, action, resource_type, resource_id=None, resource_name=None, details=None):
    log = ActivityLog(
        user_id=user.id,
        user_name=user.full_name if hasattr(user, 'full_name') else user.first_name,
        action=action,
        resource_type=resource_type,
        resource_id=int(resource_id) if resource_id else None,
        resource_name=resource_name,
        details=details if isinstance(details, dict) else {'message': details} if details else None,
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()

@search_bp.route('/api/search')
@login_required
def search_documents():
    query = request.args.get('q', '')
    category_id = request.args.get('categoryId')
    use_ai = request.args.get('ai', 'true').lower() == 'true'
    
    if not query:
        return jsonify([])
    
    log_activity(current_user, 'search', 'document', None, None, {'query': query})
    
    documents = Document.query.filter_by(is_archived=False)
    
    if category_id:
        documents = documents.filter_by(category_id=int(category_id))
    
    documents = documents.all()
    
    if use_ai and documents:
        doc_data = [{
            'id': d.id,
            'title': d.title,
            'description': d.description or '',
            'extractedText': d.extracted_text or '',
            'aiSummary': d.ai_summary or '',
            'aiKeywords': d.ai_keywords or []
        } for d in documents]
        
        ranked_ids = semantic_search(query, doc_data)
        
        doc_map = {d.id: d for d in documents}
        results = []
        for doc_id in ranked_ids:
            if doc_id in doc_map:
                results.append(doc_map[doc_id])
    else:
        search_term = f'%{query.lower()}%'
        documents = Document.query.filter_by(is_archived=False).filter(
            or_(
                Document.title.ilike(search_term),
                Document.description.ilike(search_term),
                Document.extracted_text.ilike(search_term),
                Document.ai_summary.ilike(search_term)
            )
        )
        if category_id:
            documents = documents.filter_by(category_id=int(category_id))
        results = documents.all()
    
    return jsonify([{
        'id': d.id,
        'title': d.title,
        'description': d.description,
        'fileName': d.file_name,
        'fileType': d.file_type,
        'fileSize': d.file_size,
        'categoryId': d.category_id,
        'aiSummary': d.ai_summary,
        'aiKeywords': d.ai_keywords or [],
        'createdAt': d.created_at.isoformat() if d.created_at else None,
        'category': {
            'id': d.category.id,
            'name': d.category.name
        } if d.category else None
    } for d in results])
