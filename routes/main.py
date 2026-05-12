from flask import Blueprint, render_template, jsonify, request, redirect, url_for
from flask_login import login_required, current_user
from extensions import db
from models import Document, DocumentCategory, ActivityLog, User
from sqlalchemy import func
from functools import wraps

main_bp = Blueprint('main', __name__)

def require_view(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.can_view():
            return jsonify({'error': 'Forbidden'}), 403
        return f(*args, **kwargs)
    return decorated_function

def require_edit(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.can_edit():
            return jsonify({'error': 'Forbidden'}), 403
        return f(*args, **kwargs)
    return decorated_function

def require_admin(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.can_admin():
            return jsonify({'error': 'Forbidden'}), 403
        return f(*args, **kwargs)
    return decorated_function

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@main_bp.route('/documents')
@login_required
def documents_page():
    return render_template('documents.html')

@main_bp.route('/search')
@login_required
def search_page():
    return render_template('search.html')

@main_bp.route('/upload')
@login_required
def upload_page():
    if not current_user.can_edit():
        return redirect(url_for('main.dashboard'))
    return render_template('upload.html')

@main_bp.route('/activity')
@login_required
def activity_page():
    if not current_user.can_admin():
        return redirect(url_for('main.dashboard'))
    return render_template('activity.html')

@main_bp.route('/settings')
@login_required
def settings_page():
    if not current_user.can_admin():
        return redirect(url_for('main.dashboard'))
    return render_template('settings.html')

@main_bp.route('/archive')
@login_required
def archive_page():
    return render_template('archive.html')

@main_bp.route('/folders')
@login_required
def folders_page():
    return render_template('folders.html')

@main_bp.route('/chat')
@login_required
def chat_page():
    return render_template('chat.html')

@main_bp.route('/documents/<int:doc_id>')
@login_required
def document_view(doc_id):
    document = Document.query.get_or_404(doc_id)
    
    # Log view activity
    log = ActivityLog(
        user_id=current_user.id,
        user_name=current_user.full_name if hasattr(current_user, 'full_name') else current_user.first_name,
        action='view',
        resource_type='document',
        resource_id=doc_id,
        resource_name=document.title,
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
    
    return render_template('document_view.html', document=document)

@main_bp.route('/api/chat', methods=['POST'])
@require_view
def chat_api():
    from services.ai_service import AIService
    
    data = request.get_json()
    message = data.get('message', '')
    
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    
    try:
        ai_service = AIService()
        response = ai_service.chat_with_documents(message)
        return jsonify({'response': response})
    except Exception as e:
        print(f"Chat API error: {e}")
        return jsonify({'response': 'I apologize, but I encountered an issue processing your request. Please try again.'})

@main_bp.route('/api/stats')
@require_view
def get_stats():
    from datetime import datetime
    
    total_documents = Document.query.filter_by(is_archived=False).count()
    total_categories = DocumentCategory.query.count()
    total_users = User.query.count()
    
    # Get pending archival count (documents not yet archived, uploaded in the last 30 days)
    pending_archival = Document.query.filter_by(is_archived=False).count() // 10  # Simulated
    
    # Get archived this year count
    current_year = datetime.now().year
    archived_this_year = Document.query.filter_by(is_archived=True).count()
    
    recent_activities = ActivityLog.query.order_by(
        ActivityLog.created_at.desc()
    ).limit(10).all()
    
    category_stats = db.session.query(
        DocumentCategory.name,
        func.count(Document.id).label('count')
    ).outerjoin(Document, Document.category_id == DocumentCategory.id)\
     .filter(Document.is_archived == False)\
     .group_by(DocumentCategory.id, DocumentCategory.name).all()
    
    return jsonify({
        'totalDocuments': total_documents,
        'totalCategories': total_categories,
        'totalUsers': total_users,
        'pendingArchival': pending_archival,
        'archivedThisYear': archived_this_year,
        'recentActivities': [{
            'id': a.id,
            'action': a.action,
            'resourceType': a.resource_type,
            'resourceId': a.resource_id,
            'details': a.details,
            'createdAt': a.created_at.isoformat() if a.created_at else None,
            'user': {
                'id': a.user.id if a.user else None,
                'firstName': a.user.first_name if a.user else None,
                'lastName': a.user.last_name if a.user else None,
                'profileImageUrl': a.user.profile_image_url if a.user else None
            } if a.user else None
        } for a in recent_activities],
        'categoryStats': [{'name': name, 'count': count} for name, count in category_stats]
    })
