from flask import Flask, current_app
from flask_sqlalchemy import SQLAlchemy
from os import path
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_socketio import SocketIO
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3
import datetime
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize database
db = SQLAlchemy()

# Initialize Socket.IO with proper async mode
socketio = SocketIO(
    logger=True,
    engineio_logger=True,
    cors_allowed_origins="*",
    async_mode=None  # Let SocketIO choose the best async mode
)

DB_NAME = "database.db"

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

def create_app():
    app = Flask(__name__)
    
    # Configure logging
    logging.basicConfig(level=logging.DEBUG)
    app.logger.setLevel(logging.DEBUG)
    
    # Basic configuration
    app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'False') == 'True'
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///database.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    try:
        db.init_app(app)
        migrate = Migrate(app, db)
        
        # Initialize Socket.IO with the app
        socketio.init_app(app, 
                         cors_allowed_origins="*",
                         async_mode=None)  # Let SocketIO choose the best async mode

        from .views import views 
        from .auth import auth 
        
        app.register_blueprint(auth, url_prefix='/') 
        app.register_blueprint(views, url_prefix='/') 

        from .models import User, Entry, Message, Post, Like, Comment

        # Only create tables if using SQLite
        if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
            with app.app_context():
                db.create_all()

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

        # Add error handlers
        @app.errorhandler(500)
        def internal_error(error):
            app.logger.error(f'Server Error: {error}')
            db.session.rollback()
            return "Internal Server Error: The error has been logged.", 500

        @app.errorhandler(404)
        def not_found_error(error):
            app.logger.error(f'Not Found Error: {error}')
            return "Page not found.", 404

        return app
        
    except Exception as e:
        print(f"Error creating app: {str(e)}")
        app.logger.error(f"Error creating app: {str(e)}")
        raise

def create_database(app):
    if not path.exists('website/' + DB_NAME):
        db.create_all(app=app)
        print('Created Database!')

