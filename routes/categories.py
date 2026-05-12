from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import DocumentCategory, ActivityLog

categories_bp = Blueprint('categories', __name__)

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

@categories_bp.route('/api/categories')
@login_required
def get_categories():
    categories = DocumentCategory.query.all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'description': c.description,
        'createdAt': c.created_at.isoformat() if c.created_at else None,
        'documentCount': len(c.documents)
    } for c in categories])

@categories_bp.route('/api/categories', methods=['POST'])
@login_required
def create_category():
    if not current_user.can_admin():
        return jsonify({'error': 'Forbidden - Admins only'}), 403
    
    data = request.get_json()
    
    if not data.get('name'):
        return jsonify({'error': 'Name is required'}), 400
    
    category = DocumentCategory(
        name=data['name'],
        description=data.get('description', '')
    )
    
    db.session.add(category)
    db.session.commit()
    
    log_activity(current_user, 'create', 'category', category.id, category.name)
    
    return jsonify({
        'id': category.id,
        'name': category.name,
        'description': category.description,
        'message': 'Category created successfully'
    }), 201

@categories_bp.route('/api/categories/<int:cat_id>', methods=['DELETE'])
@login_required
def delete_category(cat_id):
    if not current_user.can_admin():
        return jsonify({'error': 'Forbidden - Admins only'}), 403
    
    category = DocumentCategory.query.get_or_404(cat_id)
    
    log_activity(current_user, 'delete', 'category', cat_id, category.name)
    
    db.session.delete(category)
    db.session.commit()
    
    return jsonify({'message': 'Category deleted successfully'})
