from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from os import path
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_socketio import SocketIO
import datetime
import os

db = SQLAlchemy()
socketio = SocketIO()

def create_app():
    app = Flask(__name__)
    app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'False') == 'True'
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')
    
    # PostgreSQL Database URL configuration
    DATABASE_URL = os.getenv('DATABASE_URL')
    if DATABASE_URL:
        # Handle potential "postgres://" style URLs
        if DATABASE_URL.startswith('postgres://'):
            DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    else:
        # Fallback for development
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    print(f"Using database URL: {DATABASE_URL}")  # Debug log
    
    db.init_app(app)
    migrate = Migrate(app, db)
    socketio.init_app(app)

    from .views import views 
    from .auth import auth 
    
    app.register_blueprint(auth, url_prefix='/') 
    app.register_blueprint(views, url_prefix='/') 

    from .models import User, Entry, Message, Post, Like, Comment, CustomMetric, MetricPreference, CustomMetricEntry

    with app.app_context():
        try:
            db.create_all()
            print("Database tables created successfully")  # Debug log
        except Exception as e:
            print(f"Error creating database tables: {str(e)}")  # Debug log
            import traceback
            traceback.print_exc()

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))

    # Add timeago filter
    def timeago(timestamp):
        """Convert a timestamp to '... ago' text."""
        if timestamp is None:
            return ''

        now = datetime.datetime.now(datetime.timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)

        diff = now - timestamp

        if diff.days > 365:
            return timestamp.strftime('%d %b %Y')
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months}mo ago"
        elif diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}m ago"
        else:
            return "just now"

    app.jinja_env.filters['timeago'] = timeago

    return app

