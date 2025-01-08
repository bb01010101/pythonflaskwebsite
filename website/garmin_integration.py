import garth
import logging
from datetime import datetime, timedelta
from flask import current_app, url_for
import requests
import os
from urllib.parse import urlencode
from . import db
from .models import Activity, Entry

logger = logging.getLogger(__name__)

class GarminIntegration:
    def __init__(self, client_id=None, client_secret=None):
        self.client_id = client_id or os.environ.get('GARMIN_CLIENT_ID')
        self.client_secret = client_secret or os.environ.get('GARMIN_CLIENT_SECRET')
        self.client = None
        
        logger.info(f"Initializing GarminIntegration with client_id: {self.client_id}")
        if self.client_secret:
            logger.info("Client secret is set")
        else:
            logger.warning("Client secret is not set")

    def get_auth_url(self, redirect_uri):
        """Generate the authorization URL for Garmin OAuth"""
        try:
            logger.info(f"Generating auth URL with redirect_uri: {redirect_uri}")
            
            # Initialize Garmin client
            self.client = garth.configure()
            
            # Configure OAuth parameters
            params = {
                'client_id': self.client_id,
                'response_type': 'code',
                'redirect_uri': redirect_uri,
                'scope': 'activity:read,sleep:read'
            }
            
            # Build the authorization URL with query parameters
            auth_url = f"https://connect.garmin.com/oauth-service/oauth/authorize?{urlencode(params)}"
            logger.info(f"Generated auth URL: {auth_url}")
            return auth_url
            
        except Exception as e:
            logger.error(f"Error generating auth URL: {str(e)}", exc_info=True)
            return None

    def exchange_code_for_token(self, code, redirect_uri):
        """Exchange authorization code for access token"""
        try:
            logger.info(f"Exchanging code for token with client_id: {self.client_id}")
            logger.info(f"Redirect URI: {redirect_uri}")
            
            # Initialize Garmin client if not already initialized
            if not self.client:
                self.client = garth.configure()
            
            # Exchange the authorization code for tokens
            token_url = "https://connect.garmin.com/oauth-service/oauth/token"
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': redirect_uri
            }
            
            response = requests.post(token_url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()
            
            logger.info("Successfully exchanged code for token")
            
            # Calculate token expiration
            expires_at = datetime.now() + timedelta(seconds=token_data.get('expires_in', 3600))
            
            # Configure client with the new token
            self.client.oauth2_token = token_data.get('access_token')
            
            return {
                'access_token': token_data.get('access_token'),
                'refresh_token': token_data.get('refresh_token'),
                'expires_at': expires_at
            }
        except Exception as e:
            logger.error(f"Failed to exchange code for token: {str(e)}", exc_info=True)
            return None

    def refresh_token(self, refresh_token):
        """Refresh the access token using the refresh token"""
        try:
            token_url = "https://connect.garmin.com/oauth-service/oauth/token"
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            }
            
            response = requests.post(token_url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()
            
            # Calculate token expiration
            expires_at = datetime.now() + timedelta(seconds=token_data.get('expires_in', 3600))
            
            # Configure client with the new token
            if not self.client:
                self.client = garth.configure()
            self.client.oauth2_token = token_data.get('access_token')
            
            return {
                'access_token': token_data.get('access_token'),
                'refresh_token': token_data.get('refresh_token'),
                'expires_at': expires_at
            }
        except Exception as e:
            logger.error(f"Failed to refresh token: {str(e)}")
            return None

    def initialize_client(self, access_token):
        """Initialize the Garmin client with an access token"""
        try:
            if not self.client:
                self.client = garth.configure()
            self.client.oauth2_token = access_token
            return True
        except Exception as e:
            logger.error(f"Failed to initialize client: {str(e)}")
            return False

    def sync_activities(self, user):
        """Sync activities from Garmin"""
        if not self.client:
            if not self.initialize_client(user.garmin_access_token):
                return False

        try:
            # Check if token needs refresh
            if user.garmin_token_expires_at and user.garmin_token_expires_at <= datetime.now():
                token_response = self.refresh_token(user.garmin_refresh_token)
                if token_response:
                    user.garmin_access_token = token_response['access_token']
                    user.garmin_refresh_token = token_response['refresh_token']
                    user.garmin_token_expires_at = token_response['expires_at']
                    db.session.commit()
                    if not self.initialize_client(user.garmin_access_token):
                        return False
                else:
                    return False

            # Get the last sync time or default to 30 days ago
            last_sync = user.garmin_last_sync or (datetime.now() - timedelta(days=30))
            
            # Get activities since last sync
            activities = self.client.get_activities(start=last_sync)
            
            for activity in activities:
                # Only process running activities
                if activity.get('activityType', {}).get('typeKey') == 'running':
                    # Check if activity already exists
                    existing = Activity.query.filter_by(
                        user_id=user.id,
                        external_id=str(activity.get('activityId')),
                        source='garmin'
                    ).first()
                    
                    if not existing:
                        # Create new activity
                        new_activity = Activity(
                            user_id=user.id,
                            external_id=str(activity.get('activityId')),
                            source='garmin',
                            name=activity.get('activityName'),
                            distance=activity.get('distance', 0),  # in meters
                            duration=activity.get('duration', 0),  # in seconds
                            date=datetime.fromtimestamp(activity.get('startTimeInSeconds', 0))
                        )
                        db.session.add(new_activity)

            # Update last sync time
            user.garmin_last_sync = datetime.now()
            db.session.commit()
            return True

        except Exception as e:
            logger.error(f"Error syncing Garmin activities: {str(e)}")
            db.session.rollback()
            return False

    def sync_sleep_data(self, user):
        """Sync sleep data from Garmin"""
        if not self.client:
            if not self.initialize_client(user.garmin_access_token):
                return False

        try:
            # Check if token needs refresh
            if user.garmin_token_expires_at and user.garmin_token_expires_at <= datetime.now():
                token_response = self.refresh_token(user.garmin_refresh_token)
                if token_response:
                    user.garmin_access_token = token_response['access_token']
                    user.garmin_refresh_token = token_response['refresh_token']
                    user.garmin_token_expires_at = token_response['expires_at']
                    db.session.commit()
                    if not self.initialize_client(user.garmin_access_token):
                        return False
                else:
                    return False

            # Get today's date
            today = datetime.now().date()
            
            # Get sleep data for today
            sleep_data = self.client.get_sleep_data(today)
            
            if sleep_data and 'dailySleepDTO' in sleep_data:
                sleep_dto = sleep_data['dailySleepDTO']
                sleep_hours = sleep_dto.get('sleepTimeSeconds', 0) / 3600  # Convert seconds to hours
                
                # Check if entry exists for today
                entry = Entry.query.filter_by(
                    user_id=user.id,
                    date=today
                ).first()
                
                if entry:
                    # Update existing entry
                    entry.sleep_hours = sleep_hours
                else:
                    # Create new entry
                    entry = Entry(
                        user_id=user.id,
                        date=today,
                        sleep_hours=sleep_hours
                    )
                    db.session.add(entry)
                
                db.session.commit()
                return True

        except Exception as e:
            logger.error(f"Error syncing Garmin sleep data: {str(e)}")
            db.session.rollback()
            return False

        return False 