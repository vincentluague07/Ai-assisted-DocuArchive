import os
from flask import Flask
from dotenv import load_dotenv
from extensions import db, login_manager

load_dotenv()

def create_app():
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='static')
    
    app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    from models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(user_id)
    
    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.documents import documents_bp
    from routes.categories import categories_bp
    from routes.search import search_bp
    from routes.activity import activity_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(activity_bp)
    
    with app.app_context():
        db.create_all()
        from models import DocumentCategory
        if DocumentCategory.query.count() == 0:
            default_categories = [
                DocumentCategory(name='Board Resolutions', description='Official resolutions passed by the Board of Trustees'),
                DocumentCategory(name='Meeting Minutes', description='Minutes from Board and committee meetings'),
                DocumentCategory(name='Administrative Records', description='Administrative documents and records')
            ]
            for cat in default_categories:
                db.session.add(cat)
            db.session.commit()
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
