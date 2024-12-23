from stravalib import Client
from stravalib.exc import AccessUnauthorized
from datetime import datetime, timedelta
from flask import current_app
from . import db
from .models import User, Activity
import requests

class StravaIntegration:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.client = Client()

    def get_auth_url(self, redirect_uri):
        return self.client.authorization_url(
            client_id=self.client_id,
            redirect_uri=redirect_uri,
            scope=['read_all', 'activity:read_all']
        )

    def exchange_code_for_token(self, code):
        token_response = self.client.exchange_code_for_token(
            client_id=self.client_id,
            client_secret=self.client_secret,
            code=code
        )
        return token_response

    def sync_activities(self, user):
        try:
            self.client.access_token = user.strava_access_token
            two_weeks_ago = datetime.now() - timedelta(days=14)
            
            activities = self.client.get_activities(after=two_weeks_ago)
            
            for activity in activities:
                # Check if activity already exists
                existing_activity = Activity.query.filter_by(
                    strava_id=str(activity.id)
                ).first()
                
                if not existing_activity:
                    new_activity = Activity(
                        user_id=user.id,
                        strava_id=str(activity.id),
                        activity_type=activity.type,
                        distance=float(activity.distance.meters),
                        duration=float(activity.moving_time.total_seconds()),
                        date=activity.start_date,
                        calories=activity.calories if hasattr(activity, 'calories') else 0
                    )
                    db.session.add(new_activity)
            
            db.session.commit()
            return True
            
        except AccessUnauthorized:
            # Handle token refresh here
            return False 