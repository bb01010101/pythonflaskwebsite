from stravalib import Client
from stravalib.exc import AccessUnauthorized
from datetime import datetime, timedelta
from flask import current_app
from . import db
from .models import User, Activity, Entry
import requests
import logging

logger = logging.getLogger(__name__)

class StravaIntegration:
    def __init__(self, client_id, client_secret):
        if not client_id or not client_secret:
            logger.error("Missing Strava credentials!")
            logger.error(f"Client ID: {client_id}")
            logger.error(f"Client Secret: {client_secret}")
            raise ValueError("Strava client_id and client_secret are required")
            
        logger.info(f"Initializing StravaIntegration with client_id: {client_id}")
        self.client_id = client_id
        self.client_secret = client_secret
        self.client = Client()

    def get_auth_url(self, redirect_uri):
        logger.info(f"Generating auth URL with redirect_uri: {redirect_uri}")
        return self.client.authorization_url(
            client_id=self.client_id,
            redirect_uri=redirect_uri,
            scope=['read_all', 'activity:read_all']
        )

    def exchange_code_for_token(self, code):
        logger.info("Exchanging code for token")
        try:
            token_response = self.client.exchange_code_for_token(
                client_id=self.client_id,
                client_secret=self.client_secret,
                code=code
            )
            logger.info("Successfully exchanged code for token")
            
            # Convert token response to dictionary if it isn't already
            if not isinstance(token_response, dict):
                token_response = {
                    'access_token': token_response.access_token,
                    'refresh_token': token_response.refresh_token,
                    'expires_at': token_response.expires_at,
                    'athlete': {
                        'id': token_response.athlete.id if hasattr(token_response, 'athlete') else None
                    }
                }
            
            logger.info(f"Processed token response: {token_response}")
            return token_response
        except Exception as e:
            logger.error(f"Error exchanging code for token: {str(e)}", exc_info=True)
            raise

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
                    # Handle distance conversion
                    try:
                        if hasattr(activity.distance, 'meters'):
                            distance = float(activity.distance.meters)
                        elif hasattr(activity.distance, 'get_num'):
                            distance = float(activity.distance.get_num())
                        else:
                            distance = float(activity.distance)
                    except (AttributeError, TypeError):
                        logger.warning(f"Could not parse distance for activity {activity.id}, using 0")
                        distance = 0.0

                    # Convert meters to miles
                    distance_miles = distance * 0.000621371

                    # Get the activity date
                    activity_date = activity.start_date.date()

                    # Find or create an Entry for this date
                    entry = Entry.query.filter_by(
                        user_id=user.id,
                        date=activity_date
                    ).first()

                    if entry:
                        # Update existing entry's running mileage
                        entry.running_mileage = entry.running_mileage + distance_miles
                        logger.info(f"Updated entry for {activity_date} with additional {distance_miles} miles")
                    else:
                        # Create new entry
                        entry = Entry(
                            user_id=user.id,
                            date=activity_date,
                            running_mileage=distance_miles,
                            sleep_hours=0,
                            calories=0,
                            water_intake=0,
                            screen_time=0
                        )
                        db.session.add(entry)
                        logger.info(f"Created new entry for {activity_date} with {distance_miles} miles")

                    # Still create the Activity record
                    new_activity = Activity(
                        user_id=user.id,
                        strava_id=str(activity.id),
                        activity_type=activity.type,
                        distance=distance,
                        duration=float(activity.moving_time.total_seconds()),
                        date=activity.start_date,
                        calories=activity.calories if hasattr(activity, 'calories') else 0
                    )
                    db.session.add(new_activity)
                    logger.info(f"Adding new activity: {activity.type} - {distance}m on {activity.start_date}")
            
            db.session.commit()
            return True
            
        except AccessUnauthorized:
            logger.error("Access unauthorized when syncing activities")
            return False
        except Exception as e:
            logger.error(f"Error syncing activities: {str(e)}", exc_info=True)
            return False 