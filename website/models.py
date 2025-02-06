from . import db
from flask_login import UserMixin 
from sqlalchemy.sql import func
import datetime

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    username = db.Column(db.String(150), unique=True)
    entries = db.relationship('Entry', backref='user', lazy=True)
    messages = db.relationship('Message', backref='author', lazy=True)
    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)
    custom_metrics = db.relationship('CustomMetric', backref='creator', lazy=True)
    metric_preferences = db.relationship('MetricPreference', backref='user', lazy=True)
    
    # Strava integration fields
    strava_access_token = db.Column(db.String(100))
    strava_refresh_token = db.Column(db.String(100))
    strava_token_expires_at = db.Column(db.DateTime(timezone=True))
    strava_athlete_id = db.Column(db.String(50))
    strava_last_sync = db.Column(db.DateTime(timezone=True))
    
    # Garmin integration fields
    garmin_access_token = db.Column(db.String(100))
    garmin_refresh_token = db.Column(db.String(100))
    garmin_token_expires_at = db.Column(db.DateTime(timezone=True))
    garmin_last_sync = db.Column(db.DateTime(timezone=True))
    garmin_athlete_id = db.Column(db.String(50))
    
    # MyFitnessPal integration fields
    myfitnesspal_username = db.Column(db.String(150))
    myfitnesspal_password = db.Column(db.String(150))
    myfitnesspal_last_sync = db.Column(db.DateTime(timezone=True))
    
    # COROS integration fields
    coros_access_token = db.Column(db.String(100))
    coros_refresh_token = db.Column(db.String(100))
    coros_token_expires_at = db.Column(db.DateTime(timezone=True))
    coros_athlete_id = db.Column(db.String(50))
    coros_last_sync = db.Column(db.DateTime(timezone=True))

    def __init__(self, email, username, password):
        self.email = email
        self.username = username
        self.password = password
        # Initialize Strava fields
        self.strava_access_token = None
        self.strava_refresh_token = None
        self.strava_token_expires_at = None
        self.strava_athlete_id = None
        self.strava_last_sync = None
        # Initialize Garmin fields
        self.garmin_access_token = None
        self.garmin_refresh_token = None
        self.garmin_token_expires_at = None
        self.garmin_last_sync = None
        self.garmin_athlete_id = None
        # Initialize MyFitnessPal fields
        self.myfitnesspal_username = None
        self.myfitnesspal_password = None
        self.myfitnesspal_last_sync = None
        # Initialize COROS fields
        self.coros_access_token = None
        self.coros_refresh_token = None
        self.coros_token_expires_at = None
        self.coros_athlete_id = None
        self.coros_last_sync = None

    def sync_strava_if_needed(self):
        """Sync Strava activities if connected and last sync was more than 24 hours ago"""
        if not self.strava_access_token:
            return False
            
        now = datetime.datetime.now(datetime.timezone.utc)
        if (not self.strava_last_sync or 
            (now - self.strava_last_sync).total_seconds() > 24 * 60 * 60):
            from .views import strava_integration  # Import here to avoid circular import
            try:
                success = strava_integration.sync_activities(self)
                if success:
                    self.strava_last_sync = now
                    db.session.commit()
                return success
            except Exception as e:
                logger.error(f"Error in automatic Strava sync: {str(e)}")
                return False
        return True

class CustomMetric(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    unit = db.Column(db.String(50))
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    is_higher_better = db.Column(db.Boolean, default=True)  # True if higher values are better
    is_approved = db.Column(db.Boolean, default=False)  # Admin approval status
    metric_entries = db.relationship('CustomMetricEntry', backref='metric', lazy=True)

class CustomMetricEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    metric_id = db.Column(db.Integer, db.ForeignKey('custom_metric.id'), nullable=False)
    entry_id = db.Column(db.Integer, db.ForeignKey('entry.id'), nullable=False)
    value = db.Column(db.Float, nullable=False)

class MetricPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    metric_type = db.Column(db.String(50), nullable=False)  # 'default' or 'custom'
    metric_id = db.Column(db.Integer, db.ForeignKey('custom_metric.id'), nullable=True)  # Only for custom metrics
    is_active = db.Column(db.Boolean, default=True)
    priority = db.Column(db.Integer, default=0)  # For ordering metrics

class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=datetime.date.today)
    sleep_hours = db.Column(db.Float, default=0)
    calories = db.Column(db.Integer, default=0)
    water_intake = db.Column(db.Integer, default=0)
    running_mileage = db.Column(db.Float, default=0)
    screen_time = db.Column(db.Float, default=0)
    notes = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    custom_entries = db.relationship('CustomMetricEntry', backref='entry', lazy=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_data = db.Column(db.LargeBinary)
    image_filename = db.Column(db.String(255))
    likes = db.relationship('Like', backref='post', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref=db.backref('post_parent', lazy=True), lazy=True, cascade='all, delete-orphan')

    def like_count(self):
        return len(self.likes)

    def is_liked_by(self, user):
        return any(like.user_id == user.id for like in self.likes)

class Like(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), primary_key=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    strava_id = db.Column(db.String(50), unique=True)
    activity_type = db.Column(db.String(50))
    distance = db.Column(db.Float)  # in meters
    duration = db.Column(db.Float)  # in seconds
    date = db.Column(db.DateTime, nullable=False)
    calories = db.Column(db.Integer)
    
    user = db.relationship('User', backref=db.backref('activities', lazy=True))

class Challenge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    metric_type = db.Column(db.String(50), nullable=False)  # 'default' or 'custom'
    metric_id = db.Column(db.Integer, db.ForeignKey('custom_metric.id'), nullable=True)  # Only for custom metrics
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    is_public = db.Column(db.Boolean, default=True)
    invite_code = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    creator = db.relationship('User', backref=db.backref('created_challenges', lazy=True))
    participants = db.relationship('ChallengeParticipant', backref='challenge', lazy=True)

class ChallengeParticipant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenge.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    user = db.relationship('User', backref=db.backref('challenge_participations', lazy=True))

    def get_score(self):
        """Calculate participant's score based on challenge metric type and date range"""
        total = 0
        if self.challenge.metric_type == 'default':
            entries = Entry.query.filter(
                Entry.user_id == self.user_id,
                Entry.date >= self.challenge.start_date.date(),
                Entry.date <= self.challenge.end_date.date()
            ).all()
            
            for entry in entries:
                if self.challenge.metric_type == 'sleep_hours':
                    total += entry.sleep_hours
                elif self.challenge.metric_type == 'calories':
                    total += entry.calories
                elif self.challenge.metric_type == 'water_intake':
                    total += entry.water_intake
                elif self.challenge.metric_type == 'running_mileage':
                    total += entry.running_mileage
                elif self.challenge.metric_type == 'screen_time':
                    total += entry.screen_time
        else:
            # For custom metrics
            entries = CustomMetricEntry.query.join(Entry).filter(
                Entry.user_id == self.user_id,
                Entry.date >= self.challenge.start_date.date(),
                Entry.date <= self.challenge.end_date.date(),
                CustomMetricEntry.metric_id == self.challenge.metric_id
            ).all()
            
            for entry in entries:
                total += entry.value
                
        return total

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50))  # 'daily' or 'weekly'
    description = db.Column(db.Text, nullable=False)
    target_value = db.Column(db.Float)
    metric_type = db.Column(db.String(50))  # e.g., 'running_mileage', 'sleep_hours', etc.
    start_date = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    end_date = db.Column(db.DateTime)
    completed = db.Column(db.Boolean, default=False)
    
    user = db.relationship('User', backref=db.backref('goals', lazy=True))

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_bot = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    user = db.relationship('User', backref=db.backref('chat_messages', lazy=True))





    

