from flask import Blueprint, render_template, request, flash, redirect, url_for
from .models import User, Entry, CustomMetric, CustomMetricEntry
from werkzeug.security import generate_password_hash, check_password_hash
from . import db
from flask_login import login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
from sqlalchemy import func

auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_id = request.form.get('email')  # This will now be either email or username
        password = request.form.get('password')

        # Try to find user by email first, then by username if not found
        user = User.query.filter_by(email=login_id).first()
        if not user:
            user = User.query.filter_by(username=login_id).first()

        if user:
            if check_password_hash(user.password, password):
                flash('Login successful!', category='success')
                login_user(user, remember=True)
                return redirect(url_for('views.home'))
            else:
                flash('Incorrect password.', category='error')
        else:
            flash('Email or username not found.', category='error')

    return render_template("login.html", user=current_user)



@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth.route('/sign-up', methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')

        # Check for existing email
        email_exists = User.query.filter_by(email=email).first()
        # Check for existing username
        username_exists = User.query.filter_by(username=username).first()

        if email_exists:
            flash('Email already exists.', category='error')
        elif username_exists:
            flash('Username already taken. Please choose another.', category='error')
        elif len(email) < 4:
            flash('Email must be greater than 3 characters.', category='error')
        elif len(username) < 2:
            flash('Username must be greater than 1 character.', category='error')
        elif password1 != password2:
            flash('Passwords don\'t match.', category='error')
        elif len(password1) < 7:
            flash('Password must be at least 7 characters.', category='error')
        else:
            new_user = User(email=email, username=username, password=generate_password_hash(
                password1, method='sha256'))
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user, remember=True)
            flash('Account created!', category='success')
            return redirect(url_for('views.home'))

    return render_template("sign_up.html", user=current_user)

@auth.route('/leaderboard')
@login_required
def leaderboard():
    metric = request.args.get('metric', 'running_mileage')
    timeframe = request.args.get('timeframe', 'day')
    
    # Calculate the date range based on timeframe
    today = datetime.now().date()
    if timeframe == 'day':
        start_date = today
        end_date = today
        timeframe_display = 'Today'
    elif timeframe == 'week':
        start_date = today - timedelta(days=today.weekday())  # Monday
        end_date = start_date + timedelta(days=6)  # Sunday
        timeframe_display = 'This Week'
    elif timeframe == 'month':
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = today.replace(day=31)
        else:
            end_date = (today.replace(day=1, month=today.month + 1) - timedelta(days=1))
        timeframe_display = 'This Month'
    elif timeframe == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today.replace(month=12, day=31)
        timeframe_display = 'This Year'
    
    # Define metric mappings for default metrics
    metric_columns = {
        'running_mileage': Entry.running_mileage,
        'calories': Entry.calories,
        'water': Entry.water_intake,
        'sleep': Entry.sleep_hours,
        'screen_time': Entry.screen_time
    }
    
    metric_units = {
        'running_mileage': 'miles',
        'calories': 'kcal',
        'water': 'ml',
        'sleep': 'hours',
        'screen_time': 'hours'
    }

    # Check if metric is a custom metric
    custom_metric = None
    if metric.startswith('custom_'):
        try:
            custom_metric_id = int(metric.split('_')[1])
            custom_metric = CustomMetric.query.get(custom_metric_id)
        except (IndexError, ValueError):
            pass

    if custom_metric:
        # Query for custom metric
        query = db.session.query(
            User.id.label('user_id'),
            User.username.label('username'),
            func.sum(CustomMetricEntry.value).label('score')
        ).join(Entry).join(CustomMetricEntry).filter(
            CustomMetricEntry.metric_id == custom_metric_id,
            Entry.date >= start_date,
            Entry.date <= end_date
        ).group_by(User.id, User.username)

        # Sort based on is_higher_better flag
        if custom_metric.is_higher_better:
            query = query.order_by(func.sum(CustomMetricEntry.value).desc())
        else:
            query = query.order_by(func.sum(CustomMetricEntry.value).asc())

        metric_unit = custom_metric.unit
    else:
        # Query for default metric
        query = db.session.query(
            User.id.label('user_id'),
            User.username.label('username'),
            func.sum(metric_columns[metric]).label('score')
        ).join(Entry).filter(
            Entry.date >= start_date,
            Entry.date <= end_date
        ).group_by(User.id, User.username)

        # For screen time, sort ascending (less is better)
        if metric == 'screen_time':
            query = query.order_by(func.sum(metric_columns[metric]).asc())
        else:
            query = query.order_by(func.sum(metric_columns[metric]).desc())

        metric_unit = metric_units[metric]
    
    leaderboard_data = query.all()
    
    # Format the data for template
    leaderboard = [{
        'user_id': entry.user_id,
        'username': entry.username,
        'score': round(entry.score if entry.score else 0, 2),
        'unit': metric_unit
    } for entry in leaderboard_data]

    # Get list of custom metrics for the dropdown
    custom_metrics = CustomMetric.query.filter_by(is_approved=True).all()
    
    return render_template('leaderboard.html', 
                         leaderboard=leaderboard,
                         current_user=current_user,
                         user=current_user,
                         selected_timeframe=timeframe_display,
                         selected_metric=metric,
                         custom_metrics=custom_metrics,
                         request=request)
