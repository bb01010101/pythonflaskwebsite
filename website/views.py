from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_file
from flask_login import login_required, current_user
from .models import User, Entry, Message, Post, Like, Comment, MetricPreference, CustomMetric, CustomMetricEntry, Activity, Challenge, ChallengeParticipant, ChatMessage
from . import db
import json
from datetime import datetime, timedelta, timezone
import os
from werkzeug.utils import secure_filename
import io
import logging
from .strava_integration import StravaIntegration
from .myfitnesspal_integration import MyFitnessPalIntegration
import pytz
import jwt
from .garmin_integration import GarminIntegration
from .chatbot import chatbot
from website.chatbot import HealthChatbot

logger = logging.getLogger(__name__)

views = Blueprint('views', __name__)

#Configure image handling for database storage
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def get_strava_integration():
    client_id = os.environ.get('STRAVA_CLIENT_ID')
    client_secret = os.environ.get('STRAVA_CLIENT_SECRET')
    
    if client_id and client_secret:
        try:
            return StravaIntegration(
                client_id=client_id,
                client_secret=client_secret
            )
        except Exception as e:
            logger.error(f"Failed to initialize StravaIntegration: {e}")
            return None
    return None

strava_integration = get_strava_integration()

# Initialize MyFitnessPal integration
myfitnesspal_integration = MyFitnessPalIntegration()

# Initialize Garmin integration
garmin_client_id = os.environ.get('GARMIN_CLIENT_ID')
garmin_client_secret = os.environ.get('GARMIN_CLIENT_SECRET')

logger.info(f"Garmin Client ID: {garmin_client_id}")
if garmin_client_secret:
    logger.info("Garmin Client Secret is set")
else:
    logger.warning("Garmin Client Secret is not set")

garmin_integration = GarminIntegration(
    client_id=garmin_client_id,
    client_secret=garmin_client_secret
)

# Add some logging to debug the values
logger.info(f"Strava Client ID: {os.environ.get('STRAVA_CLIENT_ID')}")
logger.info(f"Strava Client Secret: {os.environ.get('STRAVA_CLIENT_SECRET')}")

def allowed_file(filename):
    """
    Check if the uploaded file has an allowed extension
    Returns True if the file extension is in ALLOWED_EXTENSIONS
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def fix_timestamp(timestamp):
    """
    Fix timestamps that might have incorrect year or timezone
    Args:
        timestamp: The timestamp to fix
    Returns:
        Corrected timestamp with proper timezone and year
    """
    if timestamp is None:
        return datetime.now(timezone.utc)
    
    # If timestamp has no timezone info, assume it's UTC
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    
    # Fix future dates by setting them to current year
    now = datetime.now(timezone.utc)
    if timestamp.year > now.year:
        return timestamp.replace(year=now.year)
    return timestamp

def get_user_timezone():
    """Get the timezone (always returns Eastern Time)"""
    return pytz.timezone('America/New_York')

def convert_to_user_timezone(dt):
    """Convert a datetime to Eastern Time"""
    if dt is None:
        return None
    
    # Ensure the datetime is timezone-aware
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    
    eastern_tz = pytz.timezone('America/New_York')
    return dt.astimezone(eastern_tz)

def get_user_local_date():
    """Get the current date in Eastern Time"""
    eastern_tz = pytz.timezone('America/New_York')
    return datetime.now(eastern_tz).date()

@views.route('/')
def home():
    """Home page route"""
    if current_user.is_authenticated:
        try:
            logger.info(f"User {current_user.username} accessing home page")
            # Get the user's entries for today in their timezone
            today = get_user_local_date()
            entry = Entry.query.filter_by(
                user_id=current_user.id,
                date=today
            ).first()
            
            # Get user's metric preferences
            metric_preferences = MetricPreference.query.filter_by(
                user_id=current_user.id,
                is_active=True
            ).order_by(MetricPreference.priority).all()
            
            # Get custom metrics
            custom_metrics = CustomMetric.query.filter_by(is_approved=True).all()
            
            return render_template(
                "index.html",
                user=current_user,
                today_entry=entry,
                metric_preferences=metric_preferences,
                custom_metrics=custom_metrics
            )
        except Exception as e:
            logger.error(f"Error in home route: {str(e)}", exc_info=True)
            flash('An error occurred while loading the dashboard. Please try again.', category='error')
            return render_template("index.html", user=current_user)
    return render_template("landing.html", user=current_user)

@views.route('/view_charts', methods=['GET', 'POST'])
@login_required
def view_charts():
    # Get manual entries
    entries = Entry.query.filter_by(user_id=current_user.id).order_by(Entry.date.asc()).all()
    
    # Get Strava activities
    activities = Activity.query.filter_by(user_id=current_user.id).order_by(Activity.date.asc()).all()
    
    # Prepare data for charts
    chart_data = {
        'daily': {
            'sleep_hours': {},
            'calories': {},
            'water_intake': {},
            'running_mileage': {},
            'screen_time': {}
        },
        'weekly': {
            'sleep_hours': {},
            'calories': {},
            'water_intake': {},
            'running_mileage': {},
            'screen_time': {}
        },
        'monthly': {
            'sleep_hours': {},
            'calories': {},
            'water_intake': {},
            'running_mileage': {},
            'screen_time': {}
        },
        'yearly': {
            'sleep_hours': {},
            'calories': {},
            'water_intake': {},
            'running_mileage': {},
            'screen_time': {}
        }
    }
    
    # Process daily data from manual entries
    for entry in entries:
        date_str = entry.date.strftime('%Y-%m-%d')
        # Initialize if not exists
        if date_str not in chart_data['daily']['running_mileage']:
            chart_data['daily']['running_mileage'][date_str] = 0
            
        chart_data['daily']['sleep_hours'][date_str] = entry.sleep_hours
        chart_data['daily']['calories'][date_str] = entry.calories
        chart_data['daily']['water_intake'][date_str] = entry.water_intake
        chart_data['daily']['running_mileage'][date_str] = entry.running_mileage
        chart_data['daily']['screen_time'][date_str] = entry.screen_time
        
        # Process weekly data
        week_str = entry.date.strftime('%Y-W%W')
        if week_str not in chart_data['weekly']['sleep_hours']:
            chart_data['weekly']['sleep_hours'][week_str] = 0
            chart_data['weekly']['calories'][week_str] = 0
            chart_data['weekly']['water_intake'][week_str] = 0
            chart_data['weekly']['running_mileage'][week_str] = 0
            chart_data['weekly']['screen_time'][week_str] = 0
        chart_data['weekly']['sleep_hours'][week_str] += entry.sleep_hours
        chart_data['weekly']['calories'][week_str] += entry.calories
        chart_data['weekly']['water_intake'][week_str] += entry.water_intake
        chart_data['weekly']['running_mileage'][week_str] += entry.running_mileage
        chart_data['weekly']['screen_time'][week_str] += entry.screen_time
        
        # Process monthly data
        month_str = entry.date.strftime('%Y-%m')
        if month_str not in chart_data['monthly']['sleep_hours']:
            chart_data['monthly']['sleep_hours'][month_str] = 0
            chart_data['monthly']['calories'][month_str] = 0
            chart_data['monthly']['water_intake'][month_str] = 0
            chart_data['monthly']['running_mileage'][month_str] = 0
            chart_data['monthly']['screen_time'][month_str] = 0
        chart_data['monthly']['sleep_hours'][month_str] += entry.sleep_hours
        chart_data['monthly']['calories'][month_str] += entry.calories
        chart_data['monthly']['water_intake'][month_str] += entry.water_intake
        chart_data['monthly']['running_mileage'][month_str] += entry.running_mileage
        chart_data['monthly']['screen_time'][month_str] += entry.screen_time
        
        # Process yearly data
        year_str = entry.date.strftime('%Y')
        if year_str not in chart_data['yearly']['sleep_hours']:
            chart_data['yearly']['sleep_hours'][year_str] = 0
            chart_data['yearly']['calories'][year_str] = 0
            chart_data['yearly']['water_intake'][year_str] = 0
            chart_data['yearly']['running_mileage'][year_str] = 0
            chart_data['yearly']['screen_time'][year_str] = 0
        chart_data['yearly']['sleep_hours'][year_str] += entry.sleep_hours
        chart_data['yearly']['calories'][year_str] += entry.calories
        chart_data['yearly']['water_intake'][year_str] += entry.water_intake
        chart_data['yearly']['running_mileage'][year_str] += entry.running_mileage
        chart_data['yearly']['screen_time'][year_str] += entry.screen_time
    
    # Add Strava activities to running mileage
    for activity in activities:
        date_str = activity.date.strftime('%Y-%m-%d')
        # Initialize if not exists
        if date_str not in chart_data['daily']['running_mileage']:
            chart_data['daily']['running_mileage'][date_str] = 0
        # Add Strava miles (convert from meters to miles)
        chart_data['daily']['running_mileage'][date_str] += activity.distance * 0.000621371
        
        # Add to weekly data
        week_str = activity.date.strftime('%Y-W%W')
        if week_str not in chart_data['weekly']['running_mileage']:
            chart_data['weekly']['running_mileage'][week_str] = 0
        chart_data['weekly']['running_mileage'][week_str] += activity.distance * 0.000621371
        
        # Add to monthly data
        month_str = activity.date.strftime('%Y-%m')
        if month_str not in chart_data['monthly']['running_mileage']:
            chart_data['monthly']['running_mileage'][month_str] = 0
        chart_data['monthly']['running_mileage'][month_str] += activity.distance * 0.000621371
        
        # Add to yearly data
        year_str = activity.date.strftime('%Y')
        if year_str not in chart_data['yearly']['running_mileage']:
            chart_data['yearly']['running_mileage'][year_str] = 0
        chart_data['yearly']['running_mileage'][year_str] += activity.distance * 0.000621371
    
    # Round all running mileage values to 2 decimal places
    for timeframe in ['daily', 'weekly', 'monthly', 'yearly']:
        for date_str in chart_data[timeframe]['running_mileage']:
            chart_data[timeframe]['running_mileage'][date_str] = round(chart_data[timeframe]['running_mileage'][date_str], 2)
    
    print("Manual entries found:", len(entries))  # Debug print
    print("Strava activities found:", len(activities))  # Debug print
    print("Chart data structure:", json.dumps(chart_data, indent=2))  # Debug print
    
    return render_template("view_charts.html", user=current_user, chart_data=chart_data)

@views.route('/view_data', methods=['GET', 'POST'])
@login_required
def view_data():
    # Get entries and calculate totals in a single query using SQL window functions
    entries = db.session.query(
        Entry,
        db.func.sum(Entry.sleep_hours).over(partition_by=Entry.date).label('total_sleep'),
        db.func.sum(Entry.calories).over(partition_by=Entry.date).label('total_calories'),
        db.func.sum(Entry.water_intake).over(partition_by=Entry.date).label('total_water'),
        db.func.sum(Entry.running_mileage).over(partition_by=Entry.date).label('total_miles'),
        db.func.sum(Entry.screen_time).over(partition_by=Entry.date).label('total_screen'),
        db.func.sum(Entry.cross_training_minutes).over(partition_by=Entry.date).label('total_cross_training')
    ).filter(Entry.user_id == current_user.id).order_by(Entry.date.desc(), Entry.id.desc()).all()
    
    # Group entries efficiently using a dictionary
    daily_entries = {}
    for entry_data in entries:
        entry = entry_data[0]
        date = entry.date
        
        if date not in daily_entries:
            daily_entries[date] = {
                'date': date,
                'totals': {
                    'sleep_hours': entry_data.total_sleep,
                    'calories': entry_data.total_calories,
                    'water_intake': entry_data.total_water,
                    'running_mileage': entry_data.total_miles,
                    'screen_time': entry_data.total_screen,
                    'cross_training_minutes': entry_data.total_cross_training
                },
                'entries': []
            }
        daily_entries[date]['entries'].append(entry)
    
    # Convert to list - already sorted by date desc from the query
    daily_entries = list(daily_entries.values())
    
    return render_template(
        "view_data.html",
        user=current_user,
        daily_entries=daily_entries
    )

@views.route('/add_entry', methods=['GET', 'POST'])
@login_required
def add_entry():
    if request.method == 'POST':
        # Convert date string to a datetime.date object
        date_str = request.form.get('date')
        date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.now().date()
        
        # Build new entry data efficiently
        new_entry_data = {
            'date': date,
            'user_id': current_user.id
        }
        
        # Process numeric fields efficiently
        numeric_fields = {
            'sleep_hours': float,
            'calories': int,
            'water_intake': int,
            'running_mileage': float,
            'cross_training_minutes': int
        }
        
        # Process all numeric fields in a single loop
        for field, convert_func in numeric_fields.items():
            value = request.form.get(field, '').strip()
            if value:
                try:
                    new_entry_data[field] = convert_func(value)
                except ValueError:
                    continue
        
        # Handle goals separately since they depend on their parent fields
        if 'calories' in new_entry_data:
            caloric_goal = request.form.get('caloric_goal', '').strip()
            if caloric_goal:
                try:
                    new_entry_data['caloric_goal'] = int(caloric_goal)
                except ValueError:
                    pass
        
        if 'water_intake' in new_entry_data:
            water_goal = request.form.get('water_goal', '').strip()
            if water_goal:
                try:
                    new_entry_data['water_goal'] = int(water_goal)
                except ValueError:
                    pass
        
        # Handle screen time efficiently
        screen_hours = request.form.get('screen_time_hours', '').strip()
        screen_minutes = request.form.get('screen_time_minutes', '').strip()
        
        if screen_hours or screen_minutes:
            try:
                hours = float(screen_hours) if screen_hours else 0
                minutes = float(screen_minutes) if screen_minutes else 0
                if hours > 0 or minutes > 0:
                    new_entry_data['screen_time'] = round(hours + (minutes / 60.0), 2)
            except ValueError:
                pass
        
        # Handle notes if present
        notes = request.form.get('notes', '').strip()
        if notes:
            new_entry_data['notes'] = notes
        
        # Create and add the new entry in a single operation
        new_entry = Entry(**new_entry_data)
        db.session.add(new_entry)
        db.session.commit()
        
        # Prepare feedback message efficiently
        feedback_parts = []
        if 'sleep_hours' in new_entry_data:
            feedback_parts.append(f"sleep: {new_entry_data['sleep_hours']}h")
        if 'calories' in new_entry_data:
            feedback_parts.append(f"calories: {new_entry_data['calories']}")
        if 'water_intake' in new_entry_data:
            feedback_parts.append(f"water: {new_entry_data['water_intake']}ml")
        if 'running_mileage' in new_entry_data:
            feedback_parts.append(f"miles: {new_entry_data['running_mileage']:.2f}")
        if 'cross_training_minutes' in new_entry_data:
            feedback_parts.append(f"cross training: {new_entry_data['cross_training_minutes']}min")
        if 'screen_time' in new_entry_data:
            feedback_parts.append(f"screen time: {new_entry_data['screen_time']}h")
        
        flash("Entry added! " + ", ".join(feedback_parts), category='success')
        return redirect(url_for('views.view_data'))
        
    return render_template('add_entry.html', user=current_user)

@views.route('/edit/<int:entry_id>', methods=['GET', 'POST'])
@login_required
def edit_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    
    if request.method == 'POST':
        # Process date if provided
        date_str = request.form.get('date', '').strip()
        if date_str:
            entry.date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Process numeric fields efficiently
        numeric_fields = {
            'sleep_hours': float,
            'calories': int,
            'water_intake': int,
            'running_mileage': float,
            'cross_training_minutes': int
        }
        
        # Track which fields were updated for feedback message
        updated_fields = {}
        
        # Process all numeric fields in a single loop
        for field, convert_func in numeric_fields.items():
            value = request.form.get(field, '').strip()
            if value:
                try:
                    new_value = convert_func(value)
                    setattr(entry, field, new_value)
                    updated_fields[field] = new_value
                except ValueError:
                    continue
        
        # Handle goals efficiently
        if 'calories' in updated_fields:
            caloric_goal = request.form.get('caloric_goal', '').strip()
            if caloric_goal:
                try:
                    entry.caloric_goal = int(caloric_goal)
                except ValueError:
                    pass
        
        if 'water_intake' in updated_fields:
            water_goal = request.form.get('water_goal', '').strip()
            if water_goal:
                try:
                    entry.water_goal = int(water_goal)
                except ValueError:
                    pass
        
        # Handle screen time efficiently
        screen_hours = request.form.get('screen_time_hours', '').strip()
        screen_minutes = request.form.get('screen_time_minutes', '').strip()
        
        if screen_hours or screen_minutes:
            try:
                hours = float(screen_hours) if screen_hours else 0
                minutes = float(screen_minutes) if screen_minutes else 0
                if hours > 0 or minutes > 0:
                    screen_time = round(hours + (minutes / 60.0), 2)
                    entry.screen_time = screen_time
                    updated_fields['screen_time'] = screen_time
            except ValueError:
                pass
        
        # Handle notes if present
        notes = request.form.get('notes', '').strip()
        if notes:
            entry.notes = notes
        
        # Commit changes in a single operation
        db.session.commit()
        
        # Prepare feedback message efficiently
        feedback_parts = []
        if 'sleep_hours' in updated_fields:
            feedback_parts.append(f"sleep: {updated_fields['sleep_hours']}h")
        if 'calories' in updated_fields:
            feedback_parts.append(f"calories: {updated_fields['calories']}")
        if 'water_intake' in updated_fields:
            feedback_parts.append(f"water: {updated_fields['water_intake']}ml")
        if 'running_mileage' in updated_fields:
            feedback_parts.append(f"miles: {updated_fields['running_mileage']:.2f}")
        if 'cross_training_minutes' in updated_fields:
            feedback_parts.append(f"cross training: {updated_fields['cross_training_minutes']}min")
        if 'screen_time' in updated_fields:
            feedback_parts.append(f"screen time: {updated_fields['screen_time']}h")
        
        flash("Entry updated! " + ", ".join(feedback_parts), category='success')
        return redirect(url_for('views.view_data'))

    return render_template('edit_entry.html', entry=entry, user=current_user)

@views.route('/delete/<int:entry_id>', methods=['GET'])
@login_required
def delete_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()  # Commit deletion
    return redirect(url_for('views.view_data'))

@views.route('/message_board')
@login_required
def message_board():
    """
    Display the message board with all messages
    """
    messages = Message.query.order_by(Message.timestamp.desc()).limit(50).all()
    
    # Convert messages to JSON-serializable format with proper timestamp handling
    serialized_messages = []
    for message in messages:
        # Fix timestamp if needed
        message.timestamp = fix_timestamp(message.timestamp)
        
        # Get current time in UTC
        now = datetime.now(timezone.utc)
        diff = now - message.timestamp
        
        # Format relative time
        if diff.days > 365:
            formatted_time = f"{diff.days // 365}y ago"
        elif diff.days > 30:
            formatted_time = f"{diff.days // 30}mo ago"
        elif diff.days > 0:
            formatted_time = f"{diff.days}d ago"
        elif diff.seconds >= 3600:
            formatted_time = f"{diff.seconds // 3600}h ago"
        elif diff.seconds >= 60:
            formatted_time = f"{diff.seconds // 60}m ago"
        else:
            formatted_time = "just now"
        
        serialized_messages.append({
            'id': message.id,
            'content': message.content,
            'user_id': message.user_id,
            'username': message.author.username,
            'timestamp_ms': int(message.timestamp.timestamp() * 1000),
            'formatted_time': formatted_time
        })
    
    return render_template('message_board.html', messages=serialized_messages, user=current_user)

@views.route('/send_message', methods=['POST'])
@login_required
def send_message():
    """
    Handle new message submission via regular HTTP POST
    """
    try:
        content = request.form.get('content')
        if not content:
            return jsonify({'status': 'error', 'message': 'Message cannot be empty'}), 400

        # Create message with current UTC time
        message = Message(
            content=content,
            user_id=current_user.id,
            timestamp=datetime.now(timezone.utc)
        )
        db.session.add(message)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': {
                'id': message.id,
                'content': message.content,
                'user_id': message.user_id,
                'username': current_user.username,
                'timestamp_ms': int(message.timestamp.timestamp() * 1000),
                'formatted_time': 'just now'
            }
        })
    except Exception as e:
        print(f"Error sending message: {e}")
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@views.route('/get_messages')
@login_required
def get_messages():
    """
    Endpoint to fetch new messages via polling
    """
    try:
        last_message_id = request.args.get('last_id', type=int, default=0)
        messages = Message.query.filter(Message.id > last_message_id)\
                              .order_by(Message.timestamp.desc())\
                              .limit(50).all()
        
        serialized_messages = []
        for message in messages:
            message.timestamp = fix_timestamp(message.timestamp)
            now = datetime.now(timezone.utc)
            diff = now - message.timestamp
            
            if diff.days > 365:
                formatted_time = f"{diff.days // 365}y ago"
            elif diff.days > 30:
                formatted_time = f"{diff.days // 30}mo ago"
            elif diff.days > 0:
                formatted_time = f"{diff.days}d ago"
            elif diff.seconds >= 3600:
                formatted_time = f"{diff.seconds // 3600}h ago"
            elif diff.seconds >= 60:
                formatted_time = f"{diff.seconds // 60}m ago"
            else:
                formatted_time = "just now"
            
            serialized_messages.append({
                'id': message.id,
                'content': message.content,
                'user_id': message.user_id,
                'username': message.author.username,
                'timestamp_ms': int(message.timestamp.timestamp() * 1000),
                'formatted_time': formatted_time
            })
        
        return jsonify({'status': 'success', 'messages': serialized_messages})
    except Exception as e:
        print(f"Error fetching messages: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@views.route('/posts', methods=['GET'])
@login_required
def posts():
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    # Fix timestamps before sending to template
    for post in posts:
        post.timestamp = fix_timestamp(post.timestamp)
        for comment in post.comments:
            comment.timestamp = fix_timestamp(comment.timestamp)
    return render_template('posts.html', user=current_user, posts=posts)

# Update the create-post route to store images in the database
@views.route('/create-post', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        content = request.form.get('content')
        file = request.files.get('image')
        image_data = None
        image_filename = None

        if file and allowed_file(file.filename):
            try:
                image_filename = secure_filename(file.filename)
                image_data = file.read()
            except Exception as e:
                print(f"Error processing image: {e}")
                flash('Error processing image. Please try again.', category='error')
                return redirect(url_for('views.create_post'))

        new_post = Post(
            content=content,
            image_data=image_data,
            image_filename=image_filename,
            user_id=current_user.id,
            timestamp=datetime.now(timezone.utc)
        )
        
        db.session.add(new_post)
        db.session.commit()
        flash('Post created successfully!', category='success')
        return redirect(url_for('views.posts'))
    
    return render_template('create_post.html', user=current_user)

# Add a route to serve images from the database
@views.route('/get-image/<int:post_id>')
@login_required
def get_image(post_id):
    post = Post.query.get_or_404(post_id)
    if post.image_data:
        return send_file(
            io.BytesIO(post.image_data),
            mimetype='image/jpeg',  # You might want to store and use the actual mimetype
            as_attachment=False,
            download_name=post.image_filename
        )
    return '', 404

@views.route('/like-post/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    """
    Handle post likes:
    - If user hasn't liked the post, create a new like
    - If user has already liked the post, remove the like (unlike)
    """
    post = Post.query.get_or_404(post_id)  # Get post or return 404 if not found
    like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()

    if like:
        # Unlike: Remove existing like
        db.session.delete(like)
        db.session.commit()
    else:
        # Like: Create new like
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
        db.session.commit()

    return redirect(url_for('views.posts'))

# Update the delete-post route to handle database-stored images
@views.route('/delete-post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id and current_user.username != 'bri':
        flash('You cannot delete this post!', category='error')
        return redirect(url_for('views.posts'))

    db.session.delete(post)
    db.session.commit()
    
    if current_user.username == 'bri' and post.user_id != current_user.id:
        flash('Post deleted by admin!', category='success')
    else:
        flash('Post deleted!', category='success')
    return redirect(url_for('views.posts'))

@views.route('/add-comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    content = request.form.get('content')
    if not content:
        flash('Comment cannot be empty!', category='error')
        return redirect(url_for('views.posts'))

    post = Post.query.get_or_404(post_id)
    new_comment = Comment(
        content=content,
        user_id=current_user.id,
        post_id=post_id
    )
    db.session.add(new_comment)
    db.session.commit()
    flash('Comment added!', category='success')
    return redirect(url_for('views.posts'))

@views.route('/delete-comment/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.user_id != current_user.id:
        flash('You cannot delete this comment!', category='error')
        return redirect(url_for('views.posts'))

    db.session.delete(comment)
    db.session.commit()
    flash('Comment deleted!', category='success')
    return redirect(url_for('views.posts'))

@views.route('/delete-message/<int:message_id>', methods=['POST'])
@login_required
def delete_message(message_id):
    """
    Handle message deletion:
    - Allow admin user 'bri' to delete any message
    - Allow regular users to delete only their own messages
    """
    message = Message.query.get_or_404(message_id)
    if message.user_id != current_user.id and current_user.username != 'bri':
        flash('You cannot delete this message!', category='error')
        return redirect(url_for('views.message_board'))

    db.session.delete(message)
    db.session.commit()
    
    if current_user.username == 'bri' and message.user_id != current_user.id:
        flash('Message deleted by admin!', category='success')
    else:
        flash('Message deleted!', category='success')
    return redirect(url_for('views.message_board'))

@views.route('/metric-settings', methods=['GET'])
@login_required
def metric_settings():
    """Display metric settings page with default and custom metrics"""
    # Default metrics with descriptions
    default_metrics = [
        {
            'name': 'sleep_hours',
            'display_name': 'Sleep Hours',
            'description': 'Track your daily sleep duration',
            'is_active': any(p.metric_type == 'default' and p.metric_id == 1 for p in current_user.metric_preferences)
        },
        {
            'name': 'calories',
            'display_name': 'Calories',
            'description': 'Monitor your daily caloric intake',
            'is_active': any(p.metric_type == 'default' and p.metric_id == 2 for p in current_user.metric_preferences)
        },
        {
            'name': 'water_intake',
            'display_name': 'Water Intake',
            'description': 'Track your daily water consumption',
            'is_active': any(p.metric_type == 'default' and p.metric_id == 3 for p in current_user.metric_preferences)
        },
        {
            'name': 'running_mileage',
            'display_name': 'Running Mileage',
            'description': 'Record your daily running distance',
            'is_active': any(p.metric_type == 'default' and p.metric_id == 4 for p in current_user.metric_preferences)
        },
        {
            'name': 'screen_time',
            'display_name': 'Screen Time',
            'description': 'Monitor your daily screen time',
            'is_active': any(p.metric_type == 'default' and p.metric_id == 5 for p in current_user.metric_preferences)
        }
    ]
    
    # Get approved custom metrics
    custom_metrics = CustomMetric.query.filter_by(is_approved=True).all()
    for metric in custom_metrics:
        metric.is_active = any(p.metric_type == 'custom' and p.metric_id == metric.id 
                             for p in current_user.metric_preferences)
    
    return render_template('metric_settings.html', 
                         user=current_user,
                         default_metrics=default_metrics,
                         custom_metrics=custom_metrics)

@views.route('/save-metric-preferences', methods=['POST'])
@login_required
def save_metric_preferences():
    """Save user's metric preferences"""
    try:
        # Clear existing preferences
        MetricPreference.query.filter_by(user_id=current_user.id).delete()
        
        # Save default metric preferences
        default_metrics = request.form.getlist('default_metrics')
        for i, metric_name in enumerate(default_metrics):
            pref = MetricPreference(
                user_id=current_user.id,
                metric_type='default',
                metric_id=i + 1,  # Corresponds to the order in default_metrics list
                priority=i
            )
            db.session.add(pref)
        
        # Save custom metric preferences
        custom_metrics = request.form.getlist('custom_metrics')
        for i, metric_id in enumerate(custom_metrics):
            pref = MetricPreference(
                user_id=current_user.id,
                metric_type='custom',
                metric_id=int(metric_id),
                priority=len(default_metrics) + i
            )
            db.session.add(pref)
        
        db.session.commit()
        flash('Metric preferences saved successfully!', category='success')
    except Exception as e:
        db.session.rollback()
        print(f"Error saving preferences: {e}")
        flash('Error saving preferences. Please try again.', category='error')
    
    return redirect(url_for('views.metric_settings'))

@views.route('/create-custom-metric', methods=['POST'])
@login_required
def create_custom_metric():
    """Create a new custom metric"""
    try:
        name = request.form.get('name')
        description = request.form.get('description')
        unit = request.form.get('unit')
        is_higher_better = 'is_higher_better' in request.form
        
        # Check if a similar metric already exists
        existing_metric = CustomMetric.query.filter(
            db.func.lower(CustomMetric.name) == db.func.lower(name)
        ).first()
        
        if existing_metric:
            flash('A metric with this name already exists.', category='error')
            return redirect(url_for('views.metric_settings'))
        
        # Create new custom metric
        metric = CustomMetric(
            name=name,
            description=description,
            unit=unit,
            creator_id=current_user.id,
            is_higher_better=is_higher_better,
            is_approved=current_user.username == 'bri'  # Auto-approve if creator is admin
        )
        
        db.session.add(metric)
        db.session.commit()
        
        if current_user.username == 'bri':
            flash('Custom metric created and approved!', category='success')
        else:
            flash('Custom metric created! Waiting for admin approval.', category='success')
            
    except Exception as e:
        db.session.rollback()
        print(f"Error creating metric: {e}")
        flash('Error creating custom metric. Please try again.', category='error')
    
    return redirect(url_for('views.metric_settings'))

@views.route('/delete-custom-metric/<int:metric_id>', methods=['POST'])
@login_required
def delete_custom_metric(metric_id):
    """Delete a custom metric"""
    try:
        metric = CustomMetric.query.get_or_404(metric_id)
        
        # Only allow creator or admin to delete
        if metric.creator_id != current_user.id and current_user.username != 'bri':
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
        
        # Delete associated entries and preferences
        CustomMetricEntry.query.filter_by(metric_id=metric_id).delete()
        MetricPreference.query.filter_by(metric_type='custom', metric_id=metric_id).delete()
        
        db.session.delete(metric)
        db.session.commit()
        
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting metric: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@views.route('/settings')
@login_required
def settings():
    strava_available = strava_integration is not None
    
    # Handle case where MyFitnessPal fields don't exist yet
    try:
        myfitnesspal_connected = current_user.myfitnesspal_username is not None
        myfitnesspal_last_sync = current_user.myfitnesspal_last_sync
    except:
        myfitnesspal_connected = False
        myfitnesspal_last_sync = None
    
    return render_template(
        'settings.html',
        user=current_user,
        strava_connected=current_user.strava_access_token is not None if strava_available else False,
        strava_available=strava_available,
        garmin_connected=current_user.garmin_access_token is not None,
        garmin_last_sync=current_user.garmin_last_sync,
        myfitnesspal_connected=myfitnesspal_connected,
        myfitnesspal_last_sync=myfitnesspal_last_sync
    )

@views.route('/settings-mfp', methods=['GET'])
@login_required
def settings_mfp():
    """Display MyFitnessPal settings page"""
    return render_template('settings-mfp.html', user=current_user)

@views.route('/update_timezone', methods=['POST'])
@login_required
def update_timezone():
    timezone = request.form.get('timezone')
    if timezone:
        try:
            # Validate the timezone
            pytz.timezone(timezone)
            current_user.timezone = timezone
            db.session.commit()
            flash('Time zone updated successfully!', 'success')
        except pytz.exceptions.UnknownTimeZoneError:
            flash('Invalid time zone selected.', 'error')
    else:
        flash('Please select a time zone.', 'error')
    return redirect(url_for('views.settings'))

@views.route('/strava/auth')
@login_required
def strava_auth():
    if not strava_integration:
        flash('Strava integration is not available at this time.', 'error')
        return redirect(url_for('views.settings'))
        
    redirect_uri = url_for('views.strava_callback', _external=True)
    auth_url = strava_integration.get_auth_url(redirect_uri)
    return redirect(auth_url)

@views.route('/strava/callback')
@login_required
def strava_callback():
    try:
        code = request.args.get('code')
        if not code:
            logger.error("No code received from Strava")
            flash('Authorization failed: No code received from Strava', 'error')
            return redirect(url_for('views.settings'))
            
        logger.info("Exchanging code for token...")
        token_response = strava_integration.exchange_code_for_token(code)
        logger.info(f"Received token response: {token_response}")
        
        # Store the token response values
        current_user.strava_access_token = token_response.get('access_token')
        current_user.strava_refresh_token = token_response.get('refresh_token')
        current_user.strava_token_expires_at = datetime.fromtimestamp(
            token_response.get('expires_at', 0)
        ).replace(tzinfo=timezone.utc)
        
        # Get athlete ID safely
        athlete = token_response.get('athlete', {})
        athlete_id = athlete.get('id') if isinstance(athlete, dict) else None
        
        if athlete_id:
            current_user.strava_athlete_id = str(athlete_id)
        else:
            logger.warning("No athlete ID found in token response")
            current_user.strava_athlete_id = None
        
        # Add last sync timestamp
        current_user.strava_last_sync = datetime.now(timezone.utc)
        
        logger.info("Saving tokens to database...")
        db.session.commit()
        
        logger.info("Starting initial activity sync...")
        sync_result = strava_integration.sync_activities(current_user)
        if sync_result:
            logger.info("Initial activity sync successful")
            flash('Successfully connected to Strava and synced your activities!', 'success')
        else:
            logger.warning("Activity sync failed")
            flash('Connected to Strava but failed to sync activities. Please try manual sync.', 'warning')
        
        return redirect(url_for('views.settings'))
    except Exception as e:
        logger.error(f"Error in Strava callback: {str(e)}", exc_info=True)
        flash(f'Error connecting to Strava: {str(e)}', 'error')
        return redirect(url_for('views.settings'))

@views.route('/strava/disconnect')
@login_required
def disconnect_strava():
    current_user.strava_access_token = None
    current_user.strava_refresh_token = None
    current_user.strava_token_expires_at = None
    current_user.strava_athlete_id = None
    db.session.commit()
    
    flash('Disconnected from Strava', 'success')
    return redirect(url_for('views.settings'))

@views.route('/strava/sync')
@login_required
def strava_sync():
    if not strava_integration:
        flash('Strava integration is not available at this time.', 'error')
        return redirect(url_for('views.settings'))
        
    if not current_user.strava_access_token:
        flash('Please connect your Strava account first.', 'error')
        return redirect(url_for('views.settings'))
        
    try:
        # Check if we need to sync (either manual sync or last sync was > 24 hours ago)
        last_sync = current_user.strava_last_sync
        now = datetime.now(timezone.utc)
        should_sync = (
            not last_sync or
            (now - last_sync).total_seconds() > 24 * 60 * 60 or
            request.args.get('force') == 'true'
        )
        
        if not should_sync:
            flash('Activities were synced recently. Next sync will be available in 24 hours.', 'info')
            return redirect(url_for('views.settings'))
            
        success = strava_integration.sync_activities(current_user)
        if success:
            current_user.strava_last_sync = now
            db.session.commit()
            flash('Successfully synced Strava activities!', 'success')
        else:
            flash('Failed to sync activities. Please try again later.', 'error')
            
        return redirect(url_for('views.settings'))
    except Exception as e:
        logger.error(f"Error syncing Strava activities: {str(e)}", exc_info=True)
        flash(f'Error syncing activities: {str(e)}', 'error')
        return redirect(url_for('views.settings'))

@views.route('/test_strava_data')
@login_required
def test_strava_data():
    entries = Entry.query.filter_by(user_id=current_user.id).order_by(Entry.date.desc()).all()
    data = {
        'entries': [
            {
                'date': entry.date.strftime('%Y-%m-%d'),
                'running_mileage': entry.running_mileage,
                'sleep_hours': entry.sleep_hours,
                'calories': entry.calories,
                'water_intake': entry.water_intake,
                'screen_time': entry.screen_time
            }
            for entry in entries
        ]
    }
    return jsonify(data)

@views.route('/leaderboard')
@login_required
def leaderboard():
    selected_metric = request.args.get('metric', 'running_mileage')
    selected_timeframe = request.args.get('timeframe', 'week')
    
    # Get the date range based on timeframe
    end_date = datetime.now().date()
    if selected_timeframe == 'day':
        start_date = end_date
        timeframe_text = "Today's"
    elif selected_timeframe == 'week':
        start_date = end_date - timedelta(days=end_date.weekday())
        timeframe_text = "This Week's"
    elif selected_timeframe == 'month':
        start_date = end_date.replace(day=1)
        timeframe_text = "This Month's"
    else:  # year
        start_date = end_date.replace(month=1, day=1)
        timeframe_text = "This Year's"

    # Query entries within the date range
    entries = Entry.query.filter(
        Entry.date >= start_date,
        Entry.date <= end_date
    ).all()

    # Group entries by user
    user_entries = {}
    for entry in entries:
        if entry.user_id not in user_entries:
            user_entries[entry.user_id] = []
        user_entries[entry.user_id].append(entry)

    # Calculate scores for each user
    leaderboard_data = []
    for user_id, user_entries_list in user_entries.items():
        user = User.query.get(user_id)
        if not user:
            continue

        if selected_metric == 'calories':
            # Calculate average daily adherence for the period
            total_adherence = sum(entry.get_caloric_adherence() for entry in user_entries_list)
            score = total_adherence / len(user_entries_list)
            unit = '%'
        elif selected_metric == 'water_intake':
            # Calculate average daily adherence for the period
            total_adherence = sum(entry.get_water_adherence() for entry in user_entries_list)
            score = total_adherence / len(user_entries_list)
            unit = '%'
        else:
            # For other metrics, sum the values
            score = sum(getattr(entry, selected_metric) for entry in user_entries_list)
            if selected_timeframe != 'day':
                # For longer periods, show daily average for fairness
                score = score / len(user_entries_list)
            unit = get_metric_unit(selected_metric)

        leaderboard_data.append({
            'user_id': user_id,
            'username': user.username,
            'score': score,
            'unit': unit
        })

    # Sort leaderboard
    if selected_metric in ['calories', 'water_intake']:
        # For calories and water intake, sort by how close to 100% adherence (ascending absolute difference from 100)
        leaderboard_data.sort(key=lambda x: abs(100 - x['score']))
    else:
        # For other metrics, sort by score descending
        leaderboard_data.sort(key=lambda x: x['score'], reverse=True)

    # Prepare available metrics
    available_metrics = [
        {'id': 'running_mileage', 'name': 'Running Distance'},
        {'id': 'calories', 'name': 'Caloric Goal Adherence'},
        {'id': 'water_intake', 'name': 'Water Goal Adherence'},
        {'id': 'sleep_hours', 'name': 'Sleep Hours'},
        {'id': 'screen_time', 'name': 'Screen Time'}
    ]

    return render_template(
        'leaderboard.html',
        user=current_user,
        leaderboard=leaderboard_data,
        available_metrics=available_metrics,
        selected_metric=selected_metric,
        selected_timeframe=selected_timeframe,
        timeframe_text=timeframe_text
    )

def get_metric_unit(metric):
    """Helper function to get the appropriate unit for each metric"""
    units = {
        'running_mileage': 'miles',
        'sleep_hours': 'hours',
        'calories': 'cal',
        'water_intake': 'oz',
        'screen_time': 'hours'
    }
    return units.get(metric, '')

@views.route('/privacy-policy')
def privacy_policy():
    return render_template("privacy_policy.html", user=current_user)

def timeago(timestamp):
    """Convert a timestamp to '... ago' text."""
    if timestamp is None:
        return ''

    try:
        user_tz = get_user_timezone()
        now = datetime.now(user_tz)
        
        # Convert timestamp to user's timezone
        if timestamp.tzinfo is None:
            timestamp = pytz.UTC.localize(timestamp)
        timestamp = timestamp.astimezone(user_tz)

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

@views.route('/connect_myfitnesspal', methods=['POST'])
@login_required
def connect_myfitnesspal():
    username = request.form.get('username')
    password = request.form.get('password')
    
    if not username or not password:
        flash('Please provide both email and password.', 'error')
        return redirect(url_for('views.settings'))
    
    try:
        # Try to authenticate with MyFitnessPal
        if myfitnesspal_integration.authenticate(username, password):
            # Store credentials
            current_user.myfitnesspal_username = username
            current_user.myfitnesspal_password = password
            db.session.commit()
            
            # Sync data immediately
            if myfitnesspal_integration.sync_data(current_user):
                current_user.myfitnesspal_last_sync = datetime.now(timezone.utc)
                db.session.commit()
                flash('Successfully connected to MyFitnessPal and synced data!', 'success')
            else:
                flash('Connected to MyFitnessPal but failed to sync data. Please try syncing manually.', 'warning')
        else:
            flash('Could not connect to MyFitnessPal. Please make sure you can log in to www.myfitnesspal.com with these credentials.', 'error')
    except Exception as e:
        logger.error(f"Error connecting to MyFitnessPal: {str(e)}", exc_info=True)
        if 'Invalid username or password' in str(e):
            flash('Invalid email or password. Please check your credentials and try again.', 'error')
        elif 'Network error' in str(e):
            flash('Network error while connecting to MyFitnessPal. Please try again.', 'error')
        else:
            flash('Could not connect to MyFitnessPal. Please try again in a few minutes.', 'error')
    
    return redirect(url_for('views.settings'))

@views.route('/sync_myfitnesspal')
@login_required
def sync_myfitnesspal():
    if not current_user.myfitnesspal_username:
        flash('Please connect your MyFitnessPal account first.', 'error')
        return redirect(url_for('views.settings'))
    
    try:
        # Re-authenticate with stored credentials
        if myfitnesspal_integration.authenticate(current_user.myfitnesspal_username, current_user.myfitnesspal_password):
            # Sync data
            if myfitnesspal_integration.sync_data(current_user):
                current_user.myfitnesspal_last_sync = datetime.now(timezone.utc)
                db.session.commit()
                flash('Successfully synced MyFitnessPal data!', 'success')
            else:
                flash('Failed to sync MyFitnessPal data.', 'error')
        else:
            flash('Failed to authenticate with MyFitnessPal. Please reconnect your account.', 'error')
    except Exception as e:
        logger.error(f"Error syncing MyFitnessPal data: {str(e)}", exc_info=True)
        flash('An error occurred while syncing MyFitnessPal data.', 'error')
    
    return redirect(url_for('views.settings'))

@views.route('/disconnect_myfitnesspal')
@login_required
def disconnect_myfitnesspal():
    current_user.myfitnesspal_username = None
    current_user.myfitnesspal_password = None
    current_user.myfitnesspal_last_sync = None
    db.session.commit()
    flash('Disconnected from MyFitnessPal', 'success')
    return redirect(url_for('views.settings'))

@views.route('/challenge_home')
@login_required
def challenge_home():
    """Display all public challenges and private challenges the user is part of"""
    public_challenges = Challenge.query.filter_by(is_public=True).all()
    private_challenges = Challenge.query.join(ChallengeParticipant).filter(
        Challenge.is_public == False,
        ChallengeParticipant.user_id == current_user.id
    ).all()
    
    user_challenges = set([p.challenge_id for p in current_user.challenge_participations])
    
    return render_template(
        "challenge_home.html",
        public_challenges=public_challenges,
        private_challenges=private_challenges,
        user_challenges=user_challenges,
        user=current_user
    )

@views.route('/challenge_create', methods=['GET', 'POST'])
@login_required
def challenge_create():
    """Create a new challenge"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        metric_type = request.form.get('metric_type')
        metric_id = request.form.get('metric_id')
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d')
        is_public = request.form.get('is_public') == 'true'
        invite_code = request.form.get('invite_code') if not is_public else None
        
        if not all([name, description, metric_type, start_date, end_date]):
            flash('Please fill in all required fields.', category='error')
            return redirect(url_for('views.challenge_create'))
        
        if len(name) < 3:
            flash('Challenge name must be at least 3 characters long.', category='error')
            return redirect(url_for('views.challenge_create'))

        if len(name) > 150:
            flash('Challenge name must be less than 150 characters.', category='error')
            return redirect(url_for('views.challenge_create'))

        if len(description) < 10:
            flash('Description must be at least 10 characters long.', category='error')
            return redirect(url_for('views.challenge_create'))

        if metric_type == 'custom' and not metric_id:
            flash('Please select a custom metric.', category='error')
            return redirect(url_for('views.challenge_create'))
        
        if start_date >= end_date:
            flash('End date must be after start date.', category='error')
            return redirect(url_for('views.challenge_create'))
        
        # Get current date without time
        current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        if start_date < current_date:
            flash('Start date cannot be in the past.', category='error')
            return redirect(url_for('views.challenge_create'))

        # Maximum challenge duration is 1 year
        max_end_date = start_date + timedelta(days=365)
        if end_date > max_end_date:
            flash('Challenge duration cannot exceed 1 year.', category='error')
            return redirect(url_for('views.challenge_create'))

        if not is_public and not invite_code:
            flash('Private challenges require an invite code.', category='error')
            return redirect(url_for('views.challenge_create'))
        
        if not is_public and len(invite_code) < 6:
            flash('Invite code must be at least 6 characters long.', category='error')
            return redirect(url_for('views.challenge_create'))
        
        challenge = Challenge(
            name=name,
            description=description,
            creator_id=current_user.id,
            metric_type=metric_type,
            metric_id=metric_id if metric_type == 'custom' else None,
            start_date=start_date,
            end_date=end_date,
            is_public=is_public,
            invite_code=invite_code
        )
        
        db.session.add(challenge)
        db.session.commit()
        
        # Auto-join creator to the challenge
        participant = ChallengeParticipant(
            user_id=current_user.id,
            challenge_id=challenge.id
        )
        db.session.add(participant)
        db.session.commit()
        
        if is_public:
            flash('Challenge created successfully!', category='success')
        else:
            flash('Private challenge created successfully! Share the Challenge ID and Invite Code with others to let them join.', category='success')
        return redirect(url_for('views.challenge_details', challenge_id=challenge.id))
    
    # GET request - show create form
    custom_metrics = CustomMetric.query.filter_by(is_approved=True).all()
    return render_template("challenge_create.html", custom_metrics=custom_metrics, user=current_user)

@views.route('/challenge_details/<int:challenge_id>')
@login_required
def challenge_details(challenge_id):
    """Show challenge details and leaderboard"""
    challenge = Challenge.query.get_or_404(challenge_id)
    
    # Check if user has access to private challenge
    if not challenge.is_public:
        is_participant = ChallengeParticipant.query.filter_by(
            user_id=current_user.id,
            challenge_id=challenge_id
        ).first() is not None
        
        if not is_participant:
            flash('This is a private challenge. Please enter the invite code to join.', category='error')
            return redirect(url_for('views.challenge_home'))
    
    # Get current date in user's timezone
    user_tz = get_user_timezone()
    today = datetime.now(user_tz).date()
    
    # Get date range for total timeframe
    start_date = challenge.start_date.date()
    end_date = min(challenge.end_date.date(), today)
    
    # Get participants and their scores
    participants = ChallengeParticipant.query.filter_by(challenge_id=challenge_id).all()
    leaderboard = []
    for participant in participants:
        total = 0
        if challenge.metric_type == 'custom':
            entries = CustomMetricEntry.query.join(Entry).filter(
                Entry.user_id == participant.user_id,
                Entry.date >= start_date,
                Entry.date <= end_date,
                CustomMetricEntry.metric_id == challenge.metric_id
            ).all()
            
            for entry in entries:
                total += entry.value
        else:
            entries = Entry.query.filter(
                Entry.user_id == participant.user_id,
                Entry.date >= start_date,
                Entry.date <= end_date
            ).all()
            
            for entry in entries:
                if challenge.metric_type == 'sleep_hours':
                    total += entry.sleep_hours or 0
                elif challenge.metric_type == 'calories':
                    total += entry.calories or 0
                elif challenge.metric_type == 'water_intake':
                    total += entry.water_intake or 0
                elif challenge.metric_type == 'running_mileage':
                    total += entry.running_mileage or 0
                elif challenge.metric_type == 'screen_time':
                    total += entry.screen_time or 0
        
        leaderboard.append({
            'user': participant.user,
            'score': total
        })
    
    # Sort leaderboard
    if challenge.metric_type == 'screen_time':
        leaderboard.sort(key=lambda x: x['score'])  # Ascending for screen time
    else:
        leaderboard.sort(key=lambda x: x['score'], reverse=True)  # Descending for other metrics
    
    # Check if current user is participating
    is_participant = any(p.user_id == current_user.id for p in participants)
    
    return render_template(
        "challenge_details.html",
        challenge=challenge,
        leaderboard=leaderboard,
        is_participant=is_participant,
        user=current_user
    )

@views.route('/challenge_join/<int:challenge_id>', methods=['POST'])
@login_required
def challenge_join(challenge_id):
    """Join a challenge"""
    # If challenge_id is 0, get it from the form
    if challenge_id == 0:
        try:
            challenge_id = int(request.form.get('challenge_id'))
        except (TypeError, ValueError):
            flash('Invalid challenge ID!', category='error')
            return redirect(url_for('views.challenge_home'))

    challenge = Challenge.query.get_or_404(challenge_id)
    
    # Check if already participating
    existing = ChallengeParticipant.query.filter_by(
        user_id=current_user.id,
        challenge_id=challenge_id
    ).first()
    
    if existing:
        flash('You are already participating in this challenge!', category='error')
        return redirect(url_for('views.challenge_details', challenge_id=challenge_id))
    
    # Check if user has an invite link token
    invite_token = request.args.get('invite_token')
    if invite_token:
        try:
            # Verify the invite token
            data = jwt.decode(invite_token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            if data['challenge_id'] == challenge_id:
                # Valid invite token, skip invite code check
                participant = ChallengeParticipant(
                    user_id=current_user.id,
                    challenge_id=challenge_id
                )
                db.session.add(participant)
                db.session.commit()
                flash('Successfully joined the challenge!', category='success')
                return redirect(url_for('views.challenge_details', challenge_id=challenge_id))
        except:
            # Invalid or expired token
            pass
    
    # Check invite code for private challenges
    if not challenge.is_public:
        invite_code = request.form.get('invite_code')
        if not invite_code or invite_code != challenge.invite_code:
            flash('Invalid invite code!', category='error')
            return redirect(url_for('views.challenge_home'))
    
    # Join the challenge
    participant = ChallengeParticipant(
        user_id=current_user.id,
        challenge_id=challenge_id
    )
    db.session.add(participant)
    db.session.commit()
    
    flash('Successfully joined the challenge!', category='success')
    return redirect(url_for('views.challenge_details', challenge_id=challenge_id))

@views.route('/challenge/invite/<int:challenge_id>')
@login_required
def generate_invite_link(challenge_id):
    """Generate an invite link for a challenge"""
    challenge = Challenge.query.get_or_404(challenge_id)
    
    # Check if user is the creator or admin
    if challenge.creator_id != current_user.id and current_user.username != 'bri':
        flash('You do not have permission to generate invite links for this challenge.', category='error')
        return redirect(url_for('views.challenge_details', challenge_id=challenge_id))
    
    # Generate a JWT token for the invite
    token = jwt.encode(
        {
            'challenge_id': challenge_id,
            'exp': datetime.utcnow() + timedelta(days=7)  # Token expires in 7 days
        },
        current_app.config['SECRET_KEY'],
        algorithm='HS256'
    )
    
    # Generate the full invite URL
    invite_url = url_for('views.challenge_details', challenge_id=challenge_id, invite_token=token, _external=True)
    
    return jsonify({
        'invite_url': invite_url
    })

@views.route('/challenge_leave/<int:challenge_id>', methods=['POST'])
@login_required
def challenge_leave(challenge_id):
    """Leave a challenge"""
    participant = ChallengeParticipant.query.filter_by(
        user_id=current_user.id,
        challenge_id=challenge_id
    ).first_or_404()
    
    db.session.delete(participant)
    db.session.commit()
    
    flash('Successfully left the challenge!', category='success')
    return redirect(url_for('views.challenge_home'))

@views.route('/challenge_leaderboard/<int:challenge_id>')
@login_required
def challenge_leaderboard(challenge_id):
    """Get challenge leaderboard data for a specific timeframe"""
    challenge = Challenge.query.get_or_404(challenge_id)
    timeframe = request.args.get('timeframe', 'total')
    
    # Get current date in user's timezone
    user_tz = get_user_timezone()
    today = datetime.now(user_tz).date()
    
    # Calculate date range based on timeframe
    if timeframe == 'today':
        start_date = today
        end_date = today
    elif timeframe == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    else:  # total
        start_date = challenge.start_date.date()
        end_date = min(challenge.end_date.date(), today)
    
    # Get participants and their scores for the selected timeframe
    participants = ChallengeParticipant.query.filter_by(challenge_id=challenge_id).all()
    leaderboard = []
    for participant in participants:
        total = 0
        if challenge.metric_type == 'custom':
            entries = CustomMetricEntry.query.join(Entry).filter(
                Entry.user_id == participant.user_id,
                Entry.date >= start_date,
                Entry.date <= end_date,
                CustomMetricEntry.metric_id == challenge.metric_id
            ).all()
            
            for entry in entries:
                total += entry.value
        else:
            entries = Entry.query.filter(
                Entry.user_id == participant.user_id,
                Entry.date >= start_date,
                Entry.date <= end_date
            ).all()
            
            for entry in entries:
                if challenge.metric_type == 'sleep_hours':
                    total += entry.sleep_hours or 0
                elif challenge.metric_type == 'calories':
                    total += entry.calories or 0
                elif challenge.metric_type == 'water_intake':
                    total += entry.water_intake or 0
                elif challenge.metric_type == 'running_mileage':
                    total += entry.running_mileage or 0
                elif challenge.metric_type == 'screen_time':
                    total += entry.screen_time or 0
        
        leaderboard.append({
            'user': {
                'id': participant.user.id,
                'username': participant.user.username
            },
            'score': total
        })
    
    # Sort leaderboard
    if challenge.metric_type == 'screen_time':
        leaderboard.sort(key=lambda x: x['score'])  # Ascending for screen time
    else:
        leaderboard.sort(key=lambda x: x['score'], reverse=True)  # Descending for other metrics
    
    return jsonify({'leaderboard': leaderboard})

@views.route('/challenge_delete/<int:challenge_id>', methods=['POST'])
@login_required
def challenge_delete(challenge_id):
    """Delete a challenge"""
    challenge = Challenge.query.get_or_404(challenge_id)
    
    # Check if user has permission to delete
    if challenge.creator_id != current_user.id and current_user.username != 'bri':
        flash("You don't have permission to delete this challenge.", category="error")
        return redirect(url_for("views.challenge_details", challenge_id=challenge_id))
    
    # Delete all participants first
    ChallengeParticipant.query.filter_by(challenge_id=challenge_id).delete()
    
    # Delete the challenge
    db.session.delete(challenge)
    db.session.commit()
    
    flash("Challenge deleted successfully.", category="success")
    return redirect(url_for("views.challenge_home"))

@views.route('/connect_garmin', methods=['POST'])
@login_required
def connect_garmin():
    """Connect Garmin account using email/password"""
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not email or not password:
        flash('Please provide both email and password.', 'error')
        return redirect(url_for('views.settings'))
    
    try:
        # Try to authenticate with Garmin
        if garmin_integration.authenticate(email, password):
            # Store credentials
            current_user.garmin_email = email
            current_user.garmin_password = password
            db.session.commit()
            
            # Sync data immediately
            success_activities = garmin_integration.sync_activities(current_user)
            success_sleep = garmin_integration.sync_sleep_data(current_user)
            
            if success_activities and success_sleep:
                current_user.garmin_last_sync = datetime.now(timezone.utc)
                db.session.commit()
                flash('Successfully connected to Garmin and synced data!', 'success')
            else:
                flash('Connected to Garmin but failed to sync some data. Please try syncing manually.', 'warning')
        else:
            flash('Could not connect to Garmin. Please check your credentials.', 'error')
    except Exception as e:
        logger.error(f"Error connecting to Garmin: {str(e)}", exc_info=True)
        flash('Could not connect to Garmin. Please try again.', 'error')
    
    return redirect(url_for('views.settings'))

@views.route('/garmin/auth')
@login_required
def garmin_auth():
    """Initiate Garmin OAuth flow"""
    try:
        redirect_uri = url_for('views.garmin_callback', _external=True)
        auth_url = garmin_integration.get_auth_url(redirect_uri)
        
        if not auth_url:
            flash('Error initializing Garmin connection. Please try again later.', category='error')
            return redirect(url_for('views.settings'))
            
        logger.info(f"Redirecting to Garmin auth URL: {auth_url}")
        return redirect(auth_url)
    except Exception as e:
        logger.error(f"Error in Garmin auth: {str(e)}", exc_info=True)
        flash('Error connecting to Garmin. Please try again later.', category='error')
        return redirect(url_for('views.settings'))

@views.route('/garmin/callback')
@login_required
def garmin_callback():
    """Handle Garmin OAuth callback"""
    try:
        code = request.args.get('code')
        if not code:
            logger.error("No code received from Garmin")
            flash('Authorization failed: No code received from Garmin', 'error')
            return redirect(url_for('views.settings'))
            
        logger.info(f"Received auth code from Garmin: {code[:10]}...")

        redirect_uri = url_for('views.garmin_callback', _external=True)
        logger.info(f"Using redirect URI: {redirect_uri}")
        
        token_response = garmin_integration.exchange_code_for_token(code, redirect_uri)
        logger.info(f"Token response received: {bool(token_response)}")
        
        if not token_response:
            logger.error("Failed to exchange code for token")
            flash('Failed to connect to Garmin. Please try again.', 'error')
            return redirect(url_for('views.settings'))
        
        # Store the token response values
        current_user.garmin_access_token = token_response.get('access_token')
        current_user.garmin_refresh_token = token_response.get('refresh_token')
        current_user.garmin_token_expires_at = token_response.get('expires_at')
        
        logger.info("Saving tokens to database...")
        db.session.commit()

        logger.info("Starting activity sync...")
        success_activities = garmin_integration.sync_activities(current_user)
        success_sleep = garmin_integration.sync_sleep_data(current_user)
        
        if success_activities and success_sleep:
            logger.info("Activity and sleep sync successful")
            flash('Successfully connected to Garmin!', 'success')
        else:
            logger.warning("Initial sync failed")
            flash('Connected to Garmin but failed to sync data. Please try syncing manually.', 'warning')
            
        return redirect(url_for('views.settings'))
    except Exception as e:
        logger.error(f"Error in Garmin callback: {str(e)}", exc_info=True)
        flash(f'Error connecting to Garmin: {str(e)}', 'error')
        return redirect(url_for('views.settings'))

@views.route('/garmin/sync')
@login_required
def sync_garmin():
    """Sync Garmin data"""
    if not current_user.garmin_access_token:
        flash('Please connect your Garmin account first.', 'error')
        return redirect(url_for('views.settings'))
    
    try:
        success_activities = garmin_integration.sync_activities(current_user)
        success_sleep = garmin_integration.sync_sleep_data(current_user)
        
        if success_activities and success_sleep:
            flash('Successfully synced Garmin data!', 'success')
        else:
            flash('Failed to sync Garmin data. Please try again.', 'error')
    except Exception as e:
        logger.error(f"Error syncing Garmin data: {str(e)}", exc_info=True)
        flash('An error occurred while syncing Garmin data.', 'error')
    
    return redirect(url_for('views.settings'))

@views.route('/garmin/disconnect')
@login_required
def disconnect_garmin():
    """Disconnect Garmin account"""
    current_user.garmin_access_token = None
    current_user.garmin_refresh_token = None
    current_user.garmin_token_expires_at = None
    current_user.garmin_last_sync = None
    db.session.commit()
    flash('Disconnected from Garmin', 'success')
    return redirect(url_for('views.settings'))

@views.route('/chat')
@login_required
def chat():
    """Chat interface route"""
    return render_template('chat.html', user=current_user)

@views.route('/chat/message', methods=['POST'])
@login_required
def chat_message():
    """Handle chat messages"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Save user message
        user_message = ChatMessage(
            user_id=current_user.id,
            content=message,
            is_bot=False
        )
        db.session.add(user_message)
        
        # Get bot response
        response = chatbot.process_message(current_user, message)
        
        # Save bot response
        bot_message = ChatMessage(
            user_id=current_user.id,
            content=response,
            is_bot=True
        )
        db.session.add(bot_message)
        
        db.session.commit()
        
        return jsonify({'response': response})
        
    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'An error occurred processing your message'}), 500

@views.route('/chat/history')
@login_required
def chat_history():
    """Get chat history for the current user"""
    try:
        messages = ChatMessage.query.filter_by(user_id=current_user.id).order_by(ChatMessage.timestamp).all()
        return jsonify({
            'messages': [{
                'content': msg.content,
                'is_bot': msg.is_bot,
                'timestamp': msg.timestamp.isoformat()
            } for msg in messages]
        })
    except Exception as e:
        logger.error(f"Error fetching chat history: {str(e)}", exc_info=True)
        return jsonify({'error': 'An error occurred fetching chat history'}), 500

@views.route('/set_openai_key', methods=['POST'])
@login_required
def set_openai_key():
    """Set OpenAI API key"""
    try:
        api_key = request.form.get('api_key')
        if not api_key:
            flash('API key is required', 'error')
            return redirect(url_for('views.settings'))
        
        # Set the environment variable
        os.environ['OPENAI_API_KEY'] = api_key
        
        # Reinitialize the chatbot with the new API key
        global chatbot
        chatbot = HealthChatbot()
        
        flash('OpenAI API key set successfully!', 'success')
    except Exception as e:
        logger.error(f"Error setting OpenAI API key: {str(e)}")
        flash('Error setting API key', 'error')
    
    return redirect(url_for('views.settings'))

