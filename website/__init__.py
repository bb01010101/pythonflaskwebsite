from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from os import path
from flask_login import LoginManager
from flask_migrate import Migrate
import datetime
import os
import logging


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    
    # Configure app
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
    
    logger.info(f"Using database URL: {DATABASE_URL}")
    
    try:
        db.init_app(app)
        migrate.init_app(app, db)
        logger.info("Successfully initialized database and extensions")
    except Exception as e:
        logger.error(f"Error initializing extensions: {str(e)}", exc_info=True)
        raise

    try:
        from .views import views 
        from .auth import auth 
        
        app.register_blueprint(auth, url_prefix='/') 
        app.register_blueprint(views, url_prefix='/')
        logger.info("Successfully registered blueprints") 
    except Exception as e:
        logger.error(f"Error registering blueprints: {str(e)}", exc_info=True)
        raise

    try:
        from .models import User, Entry, Message, Post, Like, Comment, CustomMetric, MetricPreference, CustomMetricEntry
    except Exception as e:
        logger.error(f"Error importing models: {str(e)}", exc_info=True)
        raise

    with app.app_context():
        try:
            db.create_all()
            logger.info("Successfully created database tables")
        except Exception as e:
            logger.error(f"Error creating database tables: {str(e)}", exc_info=True)
            raise

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    try:
        login_manager.init_app(app)
        logger.info("Successfully initialized login manager")
    except Exception as e:
        logger.error(f"Error initializing login manager: {str(e)}", exc_info=True)
        raise

    @login_manager.user_loader
    def load_user(id):
        try:
            return User.query.get(int(id))
        except Exception as e:
            logger.error(f"Error loading user {id}: {str(e)}", exc_info=True)
            return None

    # Add timeago filter
    def timeago(timestamp):
        """Convert a timestamp to '... ago' text."""
        if timestamp is None:
            return ''

        try:
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
        except Exception as e:
            logger.error(f"Error in timeago filter: {str(e)}", exc_info=True)
            return ''

    app.jinja_env.filters['timeago'] = timeago

    return app

