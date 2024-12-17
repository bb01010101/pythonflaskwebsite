from flask import Flask
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

db = SQLAlchemy()
DB_NAME = "database.db"
socketio = SocketIO()

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

def create_app():
    app = Flask(__name__)
    app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'False') == 'True'
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')
    
    # For production, use PostgreSQL
    if os.getenv('RDS_HOSTNAME'):
        db_url = (f"postgresql://{os.getenv('RDS_USERNAME')}:{os.getenv('RDS_PASSWORD')}@"
                 f"{os.getenv('RDS_HOSTNAME')}:{os.getenv('RDS_PORT')}/{os.getenv('RDS_DB_NAME')}")
        app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    migrate = Migrate(app, db)
    socketio.init_app(app)

    from .views import views 
    from .auth import auth 
    
    app.register_blueprint(auth, url_prefix='/') 
    app.register_blueprint(views, url_prefix='/') 

    from .models import User, Entry, Message

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
    
    return app

def create_database(app):
    if not path.exists('website/' + DB_NAME):
        db.create_all(app=app)
        print('Created Database!')

