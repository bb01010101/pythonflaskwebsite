from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from .models import User, Entry, Message, Post, Like, Comment
from . import db, socketio
import json
import datetime
from flask_socketio import emit
import os
from werkzeug.utils import secure_filename

views = Blueprint('views', __name__)

# Configure upload folder - use absolute path
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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

@views.route('/', methods=['GET', 'POST'])
@login_required
def home():
    """Home page route - renders the main dashboard"""
    return render_template("index.html", user=current_user)

@views.route('/view_charts', methods=['GET', 'POST'])
@login_required
def view_charts():
    entries = Entry.query.filter_by(user_id=current_user.id).order_by(Entry.date.asc()).all()
    
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
    
    # Process daily data
    for entry in entries:
        date_str = entry.date.strftime('%Y-%m-%d')
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
    
    print("Entries found:", len(entries))  # Debug print
    print("Chart data structure:", json.dumps(chart_data, indent=2))  # Debug print
    
    return render_template("view_charts.html", user=current_user, chart_data=chart_data)

@views.route('/view_data', methods=['GET', 'POST'])
@login_required
def view_data():
    entries = Entry.query.filter_by(user_id=current_user.id).order_by(Entry.date.desc()).all()
    print(f"Found {len(entries)} entries for user {current_user.id}")  # Debug print
    for entry in entries:
        print(f"Entry {entry.id}: date={entry.date}, sleep={entry.sleep_hours}, calories={entry.calories}, water={entry.water_intake}, miles={entry.running_mileage}")  # Debug print
    return render_template("view_data.html", user=current_user, entries=entries, chart_data=True)

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
    messages = Message.query.order_by(Message.timestamp.asc()).all()
    
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
            'timestamp_ms': int(message.timestamp.timestamp() * 1000),  # Convert to milliseconds
            'formatted_time': formatted_time
        })
    
    return render_template('message_board.html', messages=serialized_messages, user=current_user)

@socketio.on('new_message')
def handle_message(data):
    if not current_user.is_authenticated:
        return
    
    try:
        # Create message with current UTC time
        message = Message(
            content=data['content'],
            user_id=current_user.id,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        db.session.add(message)
        db.session.commit()
        
        # Format relative time for new message
        formatted_time = "just now"
        
        response_data = {
            'user_id': current_user.id,
            'username': current_user.username,
            'content': message.content,
            'timestamp_ms': int(message.timestamp.timestamp() * 1000),  # Convert to milliseconds
            'formatted_time': formatted_time
        }
        emit('message', response_data, broadcast=True)
    except Exception as e:
        print(f"Error handling message: {e}")
        db.session.rollback()

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

@views.route('/create-post', methods=['GET', 'POST'])
@login_required
def create_post():
    """
    Handle post creation:
    GET: Display the create post form
    POST: Process the form submission and create a new post
    """
    if request.method == 'POST':
        # Get form data
        content = request.form.get('content')
        file = request.files.get('image')
        image_path = None

        # Handle image upload if present
        if file and allowed_file(file.filename):
            # Secure the filename and add timestamp to make it unique
            filename = secure_filename(file.filename)
            filename = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            # Save the file to the upload folder
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            image_path = filename  # Store filename for database

        # Create new post with current UTC time
        new_post = Post(
            content=content,
            image_path=image_path,
            user_id=current_user.id,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        # Save to database
        db.session.add(new_post)
        db.session.commit()
        flash('Post created successfully!', category='success')
        return redirect(url_for('views.posts'))
    
    # Handle GET request - display the create post form
    return render_template('create_post.html', user=current_user)

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

@views.route('/delete-post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    """
    Handle post deletion:
    - Allow admin user 'bri' to delete any post
    - Allow regular users to delete only their own posts
    - Delete associated image file if it exists
    - Remove post from database
    """
    post = Post.query.get_or_404(post_id)
    # Check if current user is either the post author or the admin user 'bri'
    if post.user_id != current_user.id and current_user.username != 'bri':
        flash('You cannot delete this post!', category='error')
        return redirect(url_for('views.posts'))

    # Delete associated image file if it exists
    if post.image_path:
        image_path = os.path.join(UPLOAD_FOLDER, post.image_path)
        if os.path.exists(image_path):
            os.remove(image_path)

    # Delete post from database
    db.session.delete(post)
    db.session.commit()
    
    # Show appropriate success message
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

