from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String(255), primary_key=True)
    username = db.Column(db.String(100), unique=True)
    email = db.Column(db.String(255))
    password_hash = db.Column(db.String(255))
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    profile_image_url = db.Column(db.String(500))
    role = db.Column(db.String(50), default='board_trustee')  # admin, board_secretariat, board_trustee
    status = db.Column(db.String(20), default='active')  # active, inactive
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    documents = db.relationship('Document', backref='uploader', lazy=True, foreign_keys='Document.uploaded_by')
    activities = db.relationship('ActivityLog', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        return str(self.id)
    
    @property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.username or self.email or self.id
    
    def can_view(self):
        return self.role in ['admin', 'board_secretariat', 'board_trustee'] and self.status == 'active'
    
    def can_edit(self):
        return self.role in ['admin', 'board_secretariat'] and self.status == 'active'
    
    def can_admin(self):
        return self.role == 'admin' and self.status == 'active'


class DocumentCategory(db.Model):
    __tablename__ = 'document_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    documents = db.relationship('Document', backref='category', lazy=True)


class Document(db.Model):
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    file_path = db.Column(db.String(1000), nullable=False)
    file_name = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(100))
    file_size = db.Column(db.Integer)
    category_id = db.Column(db.Integer, db.ForeignKey('document_categories.id'))
    uploaded_by = db.Column(db.String(255), db.ForeignKey('users.id'))
    extracted_text = db.Column(db.Text)
    ai_summary = db.Column(db.Text)
    ai_keywords = db.Column(db.ARRAY(db.String))
    is_archived = db.Column(db.Boolean, default=False)
    version = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), db.ForeignKey('users.id'))
    user_name = db.Column(db.Text)
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(100))
    resource_id = db.Column(db.Integer)
    resource_name = db.Column(db.Text)
    details = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Session(db.Model):
    __tablename__ = 'sessions'
    
    sid = db.Column(db.String(255), primary_key=True)
    sess = db.Column(db.Text, nullable=False)
    expire = db.Column(db.DateTime, nullable=False)
