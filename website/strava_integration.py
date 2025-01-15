from stravalib import Client
from stravalib.exc import AccessUnauthorized, RateLimitExceeded
from datetime import datetime, timedelta
from flask import current_app
from . import db
from .models import User, Activity, Entry
import requests
import logging
import time

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

    def refresh_token(self, refresh_token):
        """Refresh an expired access token using the refresh token."""
        logger.info("Refreshing Strava access token")
        try:
            response = self.client.refresh_access_token(
                client_id=self.client_id,
                client_secret=self.client_secret,
                refresh_token=refresh_token
            )
            
            # Convert response to dictionary if it isn't already
            if not isinstance(response, dict):
                response = {
                    'access_token': response.access_token,
                    'refresh_token': response.refresh_token,
                    'expires_at': response.expires_at
                }
            
            logger.info("Successfully refreshed access token")
            return response
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}", exc_info=True)
            raise

    def sync_activities(self, user):
        try:
            # Check if token needs refresh
            now = datetime.now()
            if user.strava_token_expires_at and user.strava_token_expires_at <= now:
                logger.info("Access token expired, attempting to refresh")
                try:
                    new_tokens = self.refresh_token(user.strava_refresh_token)
                    user.strava_access_token = new_tokens['access_token']
                    user.strava_refresh_token = new_tokens['refresh_token']
                    user.strava_token_expires_at = datetime.fromtimestamp(new_tokens['expires_at'])
                    db.session.commit()
                    logger.info("Successfully refreshed and updated tokens")
                except Exception as e:
                    logger.error(f"Failed to refresh token: {str(e)}")
                    return False

            # Set the access token for the client
            self.client.access_token = user.strava_access_token
            
            # Get activities from the last 30 days
            one_month_ago = datetime.now() - timedelta(days=30)
            
            try:
                activities = self.client.get_activities(after=one_month_ago)
            except RateLimitExceeded:
                logger.warning("Rate limit exceeded, waiting 15 minutes before retry")
                time.sleep(900)  # Wait 15 minutes
                activities = self.client.get_activities(after=one_month_ago)
            except AccessUnauthorized:
                logger.error("Access unauthorized - token may be invalid")
                return False
            
            # Create a dictionary to accumulate daily mileage
            daily_mileage = {}
            
            # First, accumulate all mileage for each day
            for activity in activities:
                if activity.type == 'Run':  # Only process running activities
                    try:
                        if hasattr(activity.distance, 'meters'):
                            distance = float(activity.distance.meters)
                        elif hasattr(activity.distance, 'get_num'):
                            distance = float(activity.distance.get_num())
                        else:
                            distance = float(activity.distance)
                    except (AttributeError, TypeError) as e:
                        logger.warning(f"Could not parse distance for activity {activity.id}: {str(e)}")
                        continue

                    # Convert meters to miles
                    distance_miles = distance * 0.000621371
                    
                    # Get the activity date
                    activity_date = activity.start_date.date()
                    
                    # Add mileage to daily total
                    if activity_date in daily_mileage:
                        daily_mileage[activity_date] += distance_miles
                    else:
                        daily_mileage[activity_date] = distance_miles

            # Now update or create entries for each day
            for date, mileage in daily_mileage.items():
                try:
                    # Find existing entry for this date
                    entry = Entry.query.filter_by(
                        user_id=user.id,
                        date=date
                    ).first()

                    if entry:
                        # Update existing entry's running mileage while preserving other fields
                        logger.info(f"Updating entry for {date} with {mileage} miles")
                        entry.running_mileage = mileage
                    else:
                        # Create new entry with default values for other fields
                        logger.info(f"Creating new entry for {date} with {mileage} miles")
                        entry = Entry(
                            user_id=user.id,
                            date=date,
                            running_mileage=mileage,
                            sleep_hours=0,
                            calories=0,
                            water_intake=0,
                            screen_time=0,
                            notes="Auto-created from Strava sync"
                        )
                        db.session.add(entry)

                    # Commit after each entry to prevent losing all data if one fails
                    db.session.commit()
                except Exception as e:
                    logger.error(f"Error processing entry for date {date}: {str(e)}")
                    db.session.rollback()
                    continue

            logger.info(f"Successfully synced running data for {len(daily_mileage)} days")
            return True
            
        except AccessUnauthorized:
            logger.error("Access unauthorized when syncing activities")
            return False
        except Exception as e:
            logger.error(f"Error syncing activities: {str(e)}", exc_info=True)
            return False 