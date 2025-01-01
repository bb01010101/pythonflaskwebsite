from flask import current_app
from .models import User, db
from datetime import datetime, timedelta
from .strava_integration import StravaIntegration

# Get strava_integration instance from views
from .views import strava_integration

def sync_strava_activities():
    with current_app.app_context():
        users = User.query.filter(User.strava_access_token.isnot(None)).all()
        for user in users:
            try:
                # Token refresh is now handled inside sync_activities
                success = strava_integration.sync_activities(user)
                if not success:
                    current_app.logger.error(f"Failed to sync activities for user {user.id}")
            except Exception as e:
                current_app.logger.error(f"Error syncing activities for user {user.id}: {str(e)}")
                continue 