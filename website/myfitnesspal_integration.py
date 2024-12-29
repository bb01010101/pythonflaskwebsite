import myfitnesspal
from datetime import datetime, timedelta
import logging
from . import db
from .models import Entry
import requests
import os

logger = logging.getLogger(__name__)

class MyFitnessPalIntegration:
    def __init__(self):
        self.client = None

    def authenticate(self, username, password):
        """Authenticate with MyFitnessPal using email"""
        try:
            logger.info(f"Attempting to authenticate with MyFitnessPal using email: {username}")
            
            # Create a session for maintaining cookies
            session = requests.Session()
            
            # First, try to log in via the web interface
            login_url = "https://www.myfitnesspal.com/account/login"
            login_data = {
                "username": username,
                "password": password,
                "remember_me": "true"
            }
            
            # Get the login page first to get any necessary cookies
            session.get(login_url)
            
            # Attempt login
            response = session.post(login_url, data=login_data)
            
            if response.status_code != 200:
                logger.error(f"Login failed with status code: {response.status_code}")
                return False

            # Now create the client with the authenticated session
            self.client = myfitnesspal.Client(
                username=username,
                password=password,
                session=session,
                store_password=False,
                use_email_for_username=True,
                legacy_auth=True  # Use legacy authentication
            )

            # Test the connection by trying to get today's data
            today = datetime.now().date()
            day_data = self.client.get_date(today)
            logger.info(f"Successfully got data for today: {day_data}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during authentication: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error authenticating with MyFitnessPal: {str(e)}", exc_info=True)
            return False

    def sync_data(self, user):
        """Sync nutrition data from MyFitnessPal"""
        if not self.client:
            logger.error("MyFitnessPal client not authenticated")
            return False

        try:
            # Get data for the last 30 days
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)
            current_date = start_date

            while current_date <= end_date:
                try:
                    # Get day's data from MyFitnessPal
                    day = self.client.get_date(current_date)
                    
                    # Find or create entry for this date
                    entry = Entry.query.filter_by(
                        user_id=user.id,
                        date=current_date
                    ).first()

                    if not entry:
                        entry = Entry(
                            user_id=user.id,
                            date=current_date,
                            sleep_hours=0,
                            running_mileage=0,
                            screen_time=0
                        )
                        db.session.add(entry)

                    # Update calories and water intake
                    entry.calories = day.totals.get('calories', 0)
                    
                    # Convert water from mL to oz (1 mL ≈ 0.033814 oz)
                    water_ml = day.water
                    entry.water_intake = round(water_ml * 0.033814, 1) if water_ml else 0

                    logger.info(f"Synced data for {current_date}: calories={entry.calories}, water={entry.water_intake}oz")

                except Exception as e:
                    logger.error(f"Error syncing data for {current_date}: {str(e)}")
                    # Continue to next day even if this one fails
                    pass

                current_date += timedelta(days=1)

            db.session.commit()
            return True

        except Exception as e:
            logger.error(f"Error syncing MyFitnessPal data: {str(e)}", exc_info=True)
            db.session.rollback()
            return False 