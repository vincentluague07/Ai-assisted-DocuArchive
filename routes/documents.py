import os
from flask import Blueprint, request, jsonify, send_file, current_app
from flask_login import login_required, current_user
from extensions import db
from models import Document, DocumentCategory, ActivityLog
from services.document_parser import extract_text_from_file
from services.ai_service import analyze_document
from werkzeug.utils import secure_filename
import uuid

documents_bp = Blueprint('documents', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

@documents_bp.route('/api/documents')
@login_required
def get_documents():
    include_archived = request.args.get('archived', 'false').lower() == 'true'
    
    query = Document.query
    if include_archived:
        query = query.filter_by(is_archived=True)
    else:
        query = query.filter_by(is_archived=False)
    
    documents = query.order_by(Document.created_at.desc()).all()
    
    return jsonify([{
        'id': d.id,
        'title': d.title,
        'description': d.description,
        'fileName': d.file_name,
        'fileType': d.file_type,
        'fileSize': d.file_size,
        'categoryId': d.category_id,
        'uploadedBy': d.uploaded_by,
        'aiSummary': d.ai_summary,
        'aiKeywords': d.ai_keywords or [],
        'isArchived': d.is_archived,
        'version': d.version,
        'createdAt': d.created_at.isoformat() if d.created_at else None,
        'updatedAt': d.updated_at.isoformat() if d.updated_at else None,
        'category': {
            'id': d.category.id,
            'name': d.category.name,
            'description': d.category.description
        } if d.category else None,
        'uploader': {
            'id': d.uploader.id if d.uploader else None,
            'firstName': d.uploader.first_name if d.uploader else None,
            'lastName': d.uploader.last_name if d.uploader else None,
            'profileImageUrl': d.uploader.profile_image_url if d.uploader else None
        } if d.uploader else None
    } for d in documents])

@documents_bp.route('/api/documents/<int:doc_id>')
@login_required
def get_document(doc_id):
    document = Document.query.get_or_404(doc_id)
    
    log_activity(current_user, 'view', 'document', doc_id, document.title)
    
    return jsonify({
        'id': document.id,
        'title': document.title,
        'description': document.description,
        'fileName': document.file_name,
        'fileType': document.file_type,
        'fileSize': document.file_size,
        'categoryId': document.category_id,
        'uploadedBy': document.uploaded_by,
        'extractedText': document.extracted_text,
        'aiSummary': document.ai_summary,
        'aiKeywords': document.ai_keywords or [],
        'isArchived': document.is_archived,
        'version': document.version,
        'createdAt': document.created_at.isoformat() if document.created_at else None,
        'updatedAt': document.updated_at.isoformat() if document.updated_at else None,
        'category': {
            'id': document.category.id,
            'name': document.category.name,
            'description': document.category.description
        } if document.category else None
    })

@documents_bp.route('/api/documents', methods=['POST'])
@login_required
def upload_document():
    if not current_user.can_edit():
        return jsonify({'error': 'Forbidden - Editors only'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed. Allowed: PDF, DOC, DOCX, TXT'}), 400
    
    original_filename = secure_filename(file.filename)
    file_ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
    unique_filename = f"{uuid.uuid4()}.{file_ext}"
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
    
    file.save(file_path)
    file_size = os.path.getsize(file_path)
    
    title = request.form.get('title', original_filename)
    description = request.form.get('description', '')
    category_id = request.form.get('categoryId')
    if category_id:
        category_id = int(category_id)
    
    extracted_text = extract_text_from_file(file_path, file_ext)
    
    ai_result = analyze_document(extracted_text, title)
    ai_summary = ai_result.get('summary', '')
    ai_keywords = ai_result.get('keywords', [])
    
    document = Document(
        title=title,
        description=description,
        file_path=file_path,
        file_name=original_filename,
        file_type=file_ext,
        file_size=file_size,
        category_id=category_id,
        uploaded_by=current_user.id,
        extracted_text=extracted_text,
        ai_summary=ai_summary,
        ai_keywords=ai_keywords
    )
    
    db.session.add(document)
    db.session.commit()
    
    log_activity(current_user, 'upload', 'document', document.id, document.title)
    
    return jsonify({
        'id': document.id,
        'title': document.title,
        'message': 'Document uploaded successfully'
    }), 201

@documents_bp.route('/api/documents/<int:doc_id>', methods=['PUT'])
@login_required
def update_document(doc_id):
    if not current_user.can_edit():
        return jsonify({'error': 'Forbidden - Editors only'}), 403
    
    document = Document.query.get_or_404(doc_id)
    data = request.get_json()
    
    if 'title' in data:
        document.title = data['title']
    if 'description' in data:
        document.description = data['description']
    if 'categoryId' in data:
        document.category_id = data['categoryId']
    
    document.version += 1
    db.session.commit()
    
    log_activity(current_user, 'update', 'document', doc_id, document.title)
    
    return jsonify({
        'id': document.id,
        'title': document.title,
        'message': 'Document updated successfully'
    })

@documents_bp.route('/api/documents/<int:doc_id>', methods=['DELETE'])
@login_required
def delete_document(doc_id):
    if not current_user.can_edit():
        return jsonify({'error': 'Forbidden - Editors only'}), 403
    
    document = Document.query.get_or_404(doc_id)
    permanent = request.args.get('permanent', 'false').lower() == 'true'
    
    if permanent:
        if os.path.exists(document.file_path):
            os.remove(document.file_path)
        log_activity(current_user, 'permanent_delete', 'document', doc_id, document.title)
        db.session.delete(document)
    else:
        document.is_archived = True
        log_activity(current_user, 'archive', 'document', doc_id, document.title)
    
    db.session.commit()
    
    return jsonify({'message': 'Document deleted successfully'})

@documents_bp.route('/api/documents/<int:doc_id>/restore', methods=['POST'])
@login_required
def restore_document(doc_id):
    if not current_user.can_edit():
        return jsonify({'error': 'Forbidden - Editors only'}), 403
    
    document = Document.query.get_or_404(doc_id)
    document.is_archived = False
    db.session.commit()
    
    log_activity(current_user, 'restore', 'document', doc_id, document.title)
    
    return jsonify({
        'id': document.id,
        'message': 'Document restored successfully'
    })

@documents_bp.route('/api/documents/<int:doc_id>/download')
@login_required
def download_document(doc_id):
    document = Document.query.get_or_404(doc_id)
    
    if not os.path.exists(document.file_path):
        return jsonify({'error': 'File not found'}), 404
    
    log_activity(current_user, 'download', 'document', doc_id, document.title)
    
    return send_file(
        document.file_path,
        as_attachment=True,
        download_name=document.file_name
    )

@documents_bp.route('/api/documents/<int:doc_id>/preview')
@login_required
def preview_document(doc_id):
    """Serve document for inline preview (PDF, images)."""
    document = Document.query.get_or_404(doc_id)
    
    if not os.path.exists(document.file_path):
        return jsonify({'error': 'File not found'}), 404
    
    mime_types = {
        'pdf': 'application/pdf',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'txt': 'text/plain'
    }
    
    mimetype = mime_types.get(document.file_type, 'application/octet-stream')
    
    return send_file(
        document.file_path,
        mimetype=mimetype,
        as_attachment=False
    )

@documents_bp.route('/api/documents/<int:doc_id>/reindex', methods=['POST'])
@login_required
def reindex_document(doc_id):
    """Re-run AI analysis on a single document."""
    if not current_user.can_edit():
        return jsonify({'error': 'Forbidden - Editors only'}), 403
    
    document = Document.query.get_or_404(doc_id)
    
    if not document.extracted_text:
        return jsonify({'error': 'No text content to analyze'}), 400
    
    ai_result = analyze_document(document.extracted_text, document.title)
    document.ai_summary = ai_result.get('summary', '')
    document.ai_keywords = ai_result.get('keywords', [])
    
    db.session.commit()
    
    log_activity(current_user, 'update', 'document', doc_id, document.title, 
                 {'action': 'AI reindex', 'keywords_count': len(document.ai_keywords or [])})
    
    return jsonify({
        'id': document.id,
        'title': document.title,
        'aiSummary': document.ai_summary,
        'aiKeywords': document.ai_keywords,
        'message': 'Document re-indexed successfully'
    })

@documents_bp.route('/api/documents/bulk-index', methods=['POST'])
@login_required
def bulk_index_documents():
    """Bulk AI index all documents that haven't been indexed or need re-indexing."""
    if not current_user.can_admin():
        return jsonify({'error': 'Forbidden - Admins only'}), 403
    
    data = request.get_json() or {}
    force_reindex = data.get('forceReindex', False)
    
    if force_reindex:
        documents = Document.query.filter(Document.extracted_text.isnot(None)).all()
    else:
        documents = Document.query.filter(
            Document.extracted_text.isnot(None),
            (Document.ai_summary.is_(None) | (Document.ai_summary == ''))
        ).all()
    
    indexed_count = 0
    failed_count = 0
    results = []
    
    for document in documents:
        try:
            ai_result = analyze_document(document.extracted_text, document.title)
            document.ai_summary = ai_result.get('summary', '')
            document.ai_keywords = ai_result.get('keywords', [])
            indexed_count += 1
            results.append({
                'id': document.id,
                'title': document.title,
                'status': 'success'
            })
        except Exception as e:
            failed_count += 1
            results.append({
                'id': document.id,
                'title': document.title,
                'status': 'failed',
                'error': str(e)
            })
    
    db.session.commit()
    
    log_activity(current_user, 'update', 'document', None, 'Bulk AI Index',
                 {'indexed': indexed_count, 'failed': failed_count, 'force_reindex': force_reindex})
    
    return jsonify({
        'message': f'Bulk indexing complete',
        'indexed': indexed_count,
        'failed': failed_count,
        'total': len(documents),
        'results': results
    })
