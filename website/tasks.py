from flask import current_app
from .models import User
from datetime import datetime, timedelta

def sync_strava_activities():
    with current_app.app_context():
        users = User.query.filter(User.strava_access_token.isnot(None)).all()
        for user in users:
            if user.strava_token_expires_at and user.strava_token_expires_at < datetime.now():
                # Refresh token logic here
                continue
            strava_integration.sync_activities(user) 