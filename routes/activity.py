from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import ActivityLog

activity_bp = Blueprint('activity', __name__)

@activity_bp.route('/api/activity')
@login_required
def get_activity_logs():
    if not current_user.can_admin():
        return jsonify({'error': 'Forbidden - Admins only'}), 403
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('limit', 50, type=int)
    action_filter = request.args.get('action')
    resource_type_filter = request.args.get('resourceType')
    
    query = ActivityLog.query.order_by(ActivityLog.created_at.desc())
    
    if action_filter:
        query = query.filter_by(action=action_filter)
    if resource_type_filter:
        query = query.filter_by(resource_type=resource_type_filter)
    
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'logs': [{
            'id': log.id,
            'userId': log.user_id,
            'action': log.action,
            'resourceType': log.resource_type,
            'resourceId': log.resource_id,
            'details': log.details,
            'ipAddress': log.ip_address,
            'createdAt': log.created_at.isoformat() if log.created_at else None,
            'user': {
                'id': log.user.id if log.user else None,
                'firstName': log.user.first_name if log.user else None,
                'lastName': log.user.last_name if log.user else None,
                'email': log.user.email if log.user else None,
                'profileImageUrl': log.user.profile_image_url if log.user else None
            } if log.user else None
        } for log in paginated.items],
        'total': paginated.total,
        'pages': paginated.pages,
        'currentPage': page
    })
