import os
import uuid
from datetime import datetime
from flask import Blueprint, redirect, url_for, session, request, render_template, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models import User, ActivityLog

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Please enter username and password', 'error')
            return render_template('login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if not user:
            flash('Invalid username or password', 'error')
            return render_template('login.html')
        
        if user.status != 'active':
            flash('Your account is inactive. Please contact an administrator.', 'error')
            return render_template('login.html')
        
        if not user.check_password(password):
            flash('Invalid username or password', 'error')
            return render_template('login.html')
        
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        login_user(user)
        flash('Welcome back!', 'success')
        return redirect(url_for('main.dashboard'))
    
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/api/auth/user')
def get_current_user():
    if current_user.is_authenticated:
        return jsonify({
            'user': {
                'id': current_user.id,
                'username': current_user.username,
                'email': current_user.email,
                'firstName': current_user.first_name,
                'lastName': current_user.last_name,
                'profileImageUrl': current_user.profile_image_url,
                'role': current_user.role,
                'status': current_user.status,
                'lastLogin': current_user.last_login.isoformat() if current_user.last_login else None,
                'createdAt': current_user.created_at.isoformat() if current_user.created_at else None
            }
        })
    return jsonify({'user': None})

@auth_bp.route('/api/users')
@login_required
def get_users():
    if not current_user.can_admin():
        return jsonify({'error': 'Forbidden - Admins only'}), 403
    
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'firstName': u.first_name,
        'lastName': u.last_name,
        'fullName': u.full_name,
        'role': u.role,
        'status': u.status,
        'lastLogin': u.last_login.isoformat() if u.last_login else None,
        'createdAt': u.created_at.isoformat() if u.created_at else None
    } for u in users])

@auth_bp.route('/api/users', methods=['POST'])
@login_required
def create_user():
    if not current_user.can_admin():
        return jsonify({'error': 'Forbidden - Admins only'}), 403
    
    data = request.get_json()
    
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    first_name = data.get('firstName', '').strip()
    last_name = data.get('lastName', '').strip()
    role = data.get('role', 'viewer')
    
    if not username:
        return jsonify({'error': 'Username is required'}), 400
    if not password:
        return jsonify({'error': 'Password is required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    existing = User.query.filter_by(username=username).first()
    if existing:
        return jsonify({'error': 'Username already exists'}), 400
    
    user = User(
        id=str(uuid.uuid4()),
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=role,
        status='active'
    )
    user.set_password(password)
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'message': 'User created successfully'
    }), 201

@auth_bp.route('/api/users/<user_id>', methods=['PUT'])
@login_required
def update_user(user_id):
    if not current_user.can_admin():
        return jsonify({'error': 'Forbidden - Admins only'}), 403
    
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    if 'username' in data:
        new_username = data['username'].strip()
        if new_username != user.username:
            existing = User.query.filter_by(username=new_username).first()
            if existing:
                return jsonify({'error': 'Username already exists'}), 400
            user.username = new_username
    
    if 'email' in data:
        user.email = data['email'].strip()
    if 'firstName' in data:
        user.first_name = data['firstName'].strip()
    if 'lastName' in data:
        user.last_name = data['lastName'].strip()
    if 'role' in data:
        if user.id == current_user.id and data['role'] != 'admin':
            return jsonify({'error': 'Cannot remove your own admin role'}), 400
        user.role = data['role']
    if 'status' in data:
        if user.id == current_user.id and data['status'] != 'active':
            return jsonify({'error': 'Cannot deactivate your own account'}), 400
        user.status = data['status']
    if 'password' in data and data['password']:
        if len(data['password']) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        user.set_password(data['password'])
    
    db.session.commit()
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'message': 'User updated successfully'
    })

@auth_bp.route('/api/users/<user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    if not current_user.can_admin():
        return jsonify({'error': 'Forbidden - Admins only'}), 403
    
    if user_id == current_user.id:
        return jsonify({'error': 'Cannot delete your own account'}), 400
    
    user = User.query.get_or_404(user_id)
    
    try:
        # Delete activity logs for this user first (to avoid foreign key constraint)
        ActivityLog.query.filter_by(user_id=user_id).delete()
        
        # Delete the user
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({'message': 'User deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete user: {str(e)}'}), 500

@auth_bp.route('/api/users/stats')
@login_required
def get_user_stats():
    if not current_user.can_admin():
        return jsonify({'error': 'Forbidden - Admins only'}), 403
    
    total_users = User.query.count()
    active_users = User.query.filter_by(status='active').count()
    admin_count = User.query.filter_by(role='admin').count()
    secretariat_count = User.query.filter_by(role='board_secretariat').count()
    trustee_count = User.query.filter_by(role='board_trustee').count()
    
    return jsonify({
        'totalUsers': total_users,
        'activeUsers': active_users,
        'administrators': admin_count,
        'secretariat': secretariat_count,
        'trustees': trustee_count
    })
