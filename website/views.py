from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_file
from flask_login import login_required, current_user
from .models import User, Entry, Message, Post, Like, Comment, MetricPreference, CustomMetric, CustomMetricEntry, Activity, Challenge, ChallengeParticipant
from . import db
import json
import datetime
import os
from werkzeug.utils import secure_filename
import io
import logging
from .strava_integration import StravaIntegration
from .myfitnesspal_integration import MyFitnessPalIntegration
import pytz
import jwt

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
        return datetime.datetime.now(datetime.timezone.utc)
    
    # If timestamp has no timezone info, assume it's UTC
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)
    
    # Fix future dates by setting them to current year
    now = datetime.datetime.now(datetime.timezone.utc)
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
    return datetime.datetime.now(eastern_tz).date()

@views.route('/', methods=['GET', 'POST'])
@login_required
def home():
    """Home page route - renders the main dashboard"""
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
    entries = Entry.query.filter_by(user_id=current_user.id).order_by(Entry.date.desc()).all()
    logger.info(f"Found {len(entries)} entries for user {current_user.id}")
    for entry in entries:
        logger.info(f"Entry {entry.id}: date={entry.date}, miles={entry.running_mileage}")
    return render_template("view_data.html", user=current_user, entries=entries)

@views.route('/add_entry', methods=['GET', 'POST'])
@login_required
def add_entry():
    if request.method == 'POST':
        # Convert date string to a datetime.date object
        date_str = request.form.get('date', datetime.date.today().isoformat())
        date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        
        sleep_hours = float(request.form.get('sleep_hours'))
        calories = int(request.form.get('calories'))
        water_intake = float(request.form.get('hydration'))
        running_mileage = float(request.form.get('running_mileage'))
        
        # Convert screen time from hours and minutes to decimal hours
        screen_time_hours = int(request.form.get('screen_time_hours', 0))
        screen_time_minutes = int(request.form.get('screen_time_minutes', 0))
        screen_time = round(screen_time_hours + (screen_time_minutes / 60.0), 2)  # Truncate to 2 decimal places
        
        notes = request.form.get('notes')

        print(f"Adding entry for user {current_user.id} on date {date}")  # Debug print
        print(f"Data: sleep={sleep_hours}, calories={calories}, water={water_intake}, miles={running_mileage}, screen={screen_time}")  # Debug print

        # Check if an entry for this date and user already exists
        existing_entry = Entry.query.filter_by(
            date=date,
            user_id=current_user.id  # Add user_id to the filter
        ).first()
        
        if existing_entry:
            print(f"Updating existing entry {existing_entry.id}")  # Debug print
            # Update the existing entry instead of creating a new one
            existing_entry.sleep_hours = sleep_hours
            existing_entry.calories = calories
            existing_entry.water_intake = water_intake
            existing_entry.running_mileage = running_mileage
            existing_entry.screen_time = screen_time
            existing_entry.notes = notes
            db.session.commit()
            flash('Entry updated successfully!', category='success')
            return redirect(url_for('views.view_data'))
        
        # Add a new entry
        new_entry = Entry(
            date=date,
            sleep_hours=sleep_hours,
            calories=calories,
            water_intake=water_intake,
            running_mileage=running_mileage,
            screen_time=screen_time,
            notes=notes,
            user_id=current_user.id
        )
        print(f"Creating new entry for user {current_user.id}")  # Debug print
        db.session.add(new_entry)
        db.session.commit()
        flash('Entry added successfully!', category='success')
        return redirect(url_for('views.home'))
    return render_template('add_entry.html', user=current_user)

@views.route('/edit/<int:entry_id>', methods=['GET', 'POST'])
@login_required
def edit_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    
    if request.method == 'POST':
        entry.date = datetime.datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        entry.sleep_hours = float(request.form['sleep_hours'])
        entry.calories = int(request.form['calories'])
        entry.water_intake = float(request.form['hydration'])
        entry.running_mileage = float(request.form['running_mileage'])
        
        # Convert screen time from hours and minutes to decimal hours
        screen_time_hours = int(request.form.get('screen_time_hours', 0))
        screen_time_minutes = int(request.form.get('screen_time_minutes', 0))
        entry.screen_time = round(screen_time_hours + (screen_time_minutes / 60.0), 2)  # Truncate to 2 decimal places
        
        entry.notes = request.form['notes']
        
        db.session.commit()  # Save the changes
        flash('Entry updated successfully!', category='success')
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
        now = datetime.datetime.now(datetime.timezone.utc)
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
            timestamp=datetime.datetime.now(datetime.timezone.utc)
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
            now = datetime.datetime.now(datetime.timezone.utc)
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
            timestamp=datetime.datetime.now(datetime.timezone.utc)
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
        current_user.strava_token_expires_at = datetime.datetime.fromtimestamp(token_response.get('expires_at', 0))
        
        # Get athlete ID safely
        athlete = token_response.get('athlete', {})
        athlete_id = athlete.get('id') if isinstance(athlete, dict) else None
        
        if athlete_id:
            current_user.strava_athlete_id = str(athlete_id)
        else:
            logger.warning("No athlete ID found in token response")
            current_user.strava_athlete_id = None
        
        logger.info("Saving tokens to database...")
        db.session.commit()
        
        logger.info("Starting activity sync...")
        sync_result = strava_integration.sync_activities(current_user)
        if sync_result:
            logger.info("Activity sync successful")
        else:
            logger.warning("Activity sync returned False")
        
        flash('Successfully connected to Strava!', 'success')
        return redirect(url_for('views.settings'))
    except Exception as e:
        logger.error(f"Error in Strava callback: {str(e)}", exc_info=True)
        logger.error(f"Token response: {token_response}")  # Add this for debugging
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
        # Token refresh is now handled inside sync_activities
        success = strava_integration.sync_activities(current_user)
        if success:
            flash('Successfully synced Strava activities!', 'success')
        else:
            # If sync failed, it might be due to an invalid refresh token
            # Clear the tokens and ask user to reconnect
            current_user.strava_access_token = None
            current_user.strava_refresh_token = None
            current_user.strava_token_expires_at = None
            current_user.strava_athlete_id = None
            db.session.commit()
            flash('Failed to sync Strava activities. Please reconnect your account.', 'error')
    except Exception as e:
        logger.error(f"Error syncing Strava activities: {str(e)}", exc_info=True)
        flash('Error syncing activities. Please try again.', 'error')
        
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
    metric = request.args.get('metric', 'running_mileage')
    timeframe = request.args.get('timeframe', 'week')
    
    user_tz = get_user_timezone()
    today = datetime.datetime.now(user_tz).date()
    
    # Calculate date ranges in user's timezone
    if timeframe == 'day':
        start_date = today
        end_date = today
    elif timeframe == 'week':
        start_date = today - datetime.timedelta(days=today.weekday())
        end_date = today
    elif timeframe == 'month':
        start_date = today.replace(day=1)
        end_date = today
    else:  # year
        start_date = today.replace(month=1, day=1)
        end_date = today
    
    logger.info(f"Leaderboard request - Metric: {metric}, Timeframe: {timeframe}")
    logger.info(f"Date range: {start_date} to {end_date}")
    
    leaderboard_data = []
    users = User.query.all()
    
    for user in users:
        # Get entries for the user within the date range
        entries = Entry.query.filter(
            Entry.user_id == user.id,
            Entry.date >= start_date,
            Entry.date <= end_date
        ).all()
        
        # Get Strava activities if metric is running_mileage
        if metric == 'running_mileage':
            # Convert dates to datetime with user's timezone
            start_datetime = datetime.datetime.combine(start_date, datetime.time.min)
            end_datetime = datetime.datetime.combine(end_date, datetime.time.max)
            start_datetime = user_tz.localize(start_datetime)
            end_datetime = user_tz.localize(end_datetime)
            
            activities = Activity.query.filter(
                Activity.user_id == user.id,
                Activity.date >= start_datetime,
                Activity.date <= end_datetime
            ).all()
        else:
            activities = []
        
        # Calculate total value
        total_value = 0
        
        # Add up values from manual entries
        for entry in entries:
            if hasattr(entry, metric):
                metric_value = getattr(entry, metric)
                if metric_value is not None:
                    total_value += metric_value
        
        # Add Strava activities if applicable
        if metric == 'running_mileage':
            for activity in activities:
                if activity.distance:
                    # Convert meters to miles
                    total_value += activity.distance * 0.000621371
        
        # Only add to leaderboard if they have a value greater than 0
        if total_value > 0:
            logger.info(f"User {user.username} - {metric}: {total_value}")
            leaderboard_data.append({
                'user_id': user.id,
                'username': user.username,
                'score': round(float(total_value), 2),
                'unit': get_metric_unit(metric)
            })
    
    # Sort by score descending
    if metric == 'screen_time':
        leaderboard_data.sort(key=lambda x: x['score'])  # Ascending for screen time
    else:
        leaderboard_data.sort(key=lambda x: x['score'], reverse=True)  # Descending for other metrics
    
    timeframe_text = {
        'day': 'Today',
        'week': 'This Week',
        'month': 'This Month',
        'year': 'This Year'
    }.get(timeframe, 'This Week')
    
    available_metrics = [
        {'id': 'running_mileage', 'name': 'Running Mileage', 'unit': 'miles'},
        {'id': 'sleep_hours', 'name': 'Sleep Hours', 'unit': 'hours'},
        {'id': 'calories', 'name': 'Calories', 'unit': 'cal'},
        {'id': 'water_intake', 'name': 'Water Intake', 'unit': 'oz'},
        {'id': 'screen_time', 'name': 'Screen Time', 'unit': 'hours'}
    ]
    
    return render_template('leaderboard.html',
                         user=current_user,
                         leaderboard=leaderboard_data,
                         selected_metric=metric,
                         selected_timeframe=timeframe,
                         timeframe_text=timeframe_text,
                         available_metrics=available_metrics)

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

@views.route('/privacy_policy')
def privacy_policy():
    """Privacy Policy page route"""
    return render_template("privacy_policy.html", user=current_user)

def timeago(timestamp):
    """Convert a timestamp to '... ago' text."""
    if timestamp is None:
        return ''

    try:
        user_tz = get_user_timezone()
        now = datetime.datetime.now(user_tz)
        
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
                current_user.myfitnesspal_last_sync = datetime.datetime.now(datetime.timezone.utc)
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
                current_user.myfitnesspal_last_sync = datetime.datetime.now(datetime.timezone.utc)
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
        start_date = datetime.datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
        end_date = datetime.datetime.strptime(request.form.get('end_date'), '%Y-%m-%d')
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
        current_date = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        if start_date < current_date:
            flash('Start date cannot be in the past.', category='error')
            return redirect(url_for('views.challenge_create'))

        # Maximum challenge duration is 1 year
        max_end_date = start_date + datetime.timedelta(days=365)
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
    today = datetime.datetime.now(user_tz).date()
    
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
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)  # Token expires in 7 days
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
    today = datetime.datetime.now(user_tz).date()
    
    # Calculate date range based on timeframe
    if timeframe == 'today':
        start_date = today
        end_date = today
    elif timeframe == 'week':
        start_date = today - datetime.timedelta(days=today.weekday())
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

