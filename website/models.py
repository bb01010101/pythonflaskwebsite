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





    

