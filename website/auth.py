from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from .models import User, Entry
from werkzeug.security import generate_password_hash, check_password_hash
from . import db
from flask_login import login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
from sqlalchemy import func
import logging

auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if request.method == 'POST':
            login_id = request.form.get('email')  # This will now be either email or username
            password = request.form.get('password')

            current_app.logger.info(f"Login attempt for: {login_id}")

            if not login_id or not password:
                flash('Please fill in all fields.', category='error')
                return render_template("login.html", user=current_user)

            # Try to find user by email first, then by username if not found
            user = User.query.filter_by(email=login_id).first()
            if not user:
                user = User.query.filter_by(username=login_id).first()

            if user:
                if check_password_hash(user.password, password):
                    flash('Login successful!', category='success')
                    login_user(user, remember=True)
                    current_app.logger.info(f"Successful login for user: {user.username}")
                    return redirect(url_for('views.home'))
                else:
                    current_app.logger.warning(f"Failed login attempt (incorrect password) for: {login_id}")
                    flash('Incorrect password.', category='error')
            else:
                current_app.logger.warning(f"Failed login attempt (user not found) for: {login_id}")
                flash('Email or username not found.', category='error')

    except Exception as e:
        current_app.logger.error(f"Error during login: {str(e)}")
        db.session.rollback()
        flash('An error occurred during login. Please try again.', category='error')

    return render_template("login.html", user=current_user)



@auth.route('/logout')
@login_required
def logout():
    try:
        username = current_user.username
        logout_user()
        current_app.logger.info(f"User logged out: {username}")
        flash('Logged out successfully!', category='success')
    except Exception as e:
        current_app.logger.error(f"Error during logout: {str(e)}")
        flash('An error occurred during logout.', category='error')
    return redirect(url_for('auth.login'))

@auth.route('/sign-up', methods=['GET', 'POST'])
def sign_up():
    try:
        if request.method == 'POST':
            email = request.form.get('email')
            username = request.form.get('username')
            password1 = request.form.get('password1')
            password2 = request.form.get('password2')

            current_app.logger.info(f"Sign-up attempt for email: {email}, username: {username}")

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
                new_user = User(
                    email=email,
                    username=username,
                    password=generate_password_hash(password1, method='sha256')
                )
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user, remember=True)
                current_app.logger.info(f"New user created: {username}")
                flash('Account created successfully!', category='success')
                return redirect(url_for('views.home'))

    except Exception as e:
        current_app.logger.error(f"Error during sign-up: {str(e)}")
        db.session.rollback()
        flash('An error occurred during sign-up. Please try again.', category='error')

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
    elif timeframe == 'week':
        # Start from Monday of current week and include all days up to Sunday
        start_date = today - timedelta(days=today.weekday())  # Monday
        end_date = start_date + timedelta(days=6)  # Sunday
    elif timeframe == 'month':
        # Start from first day of current month
        start_date = today.replace(day=1)
        # Last day of current month
        if today.month == 12:
            end_date = today.replace(day=31)
        else:
            end_date = (today.replace(day=1, month=today.month + 1) - timedelta(days=1))
    elif timeframe == 'year':
        # Start from first day of current year
        start_date = today.replace(month=1, day=1)
        # Last day of current year
        end_date = today.replace(month=12, day=31)
    
    print(f"Date range: {start_date} to {end_date}")  # Debug print
    
    # Define metric mappings
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
    
    # Query to get aggregated data for the leaderboard
    query = db.session.query(
        User.id.label('user_id'),
        User.username.label('username'),
        func.sum(metric_columns[metric]).label('score')
    ).join(Entry).filter(
        Entry.date >= start_date,
        Entry.date <= (end_date if timeframe != 'day' else today)
    ).group_by(User.id, User.username)

    # For screen time, we want to sort ascending (less is better)
    if metric == 'screen_time':
        query = query.order_by(func.sum(metric_columns[metric]).asc())
    else:
        query = query.order_by(func.sum(metric_columns[metric]).desc())
    
    print(f"SQL Query: {query}")  # Debug print
    
    leaderboard_data = query.all()
    print(f"Leaderboard data: {leaderboard_data}")  # Debug print
    
    # Format the data for template
    leaderboard = [{
        'user_id': entry.user_id,
        'username': entry.username,
        'score': round(entry.score, 2) if entry.score else 0,
        'unit': metric_units[metric]
    } for entry in leaderboard_data]
    
    # Add timeframe to template for display
    timeframe_display = {
        'day': 'Today',
        'week': 'This Week',
        'month': 'This Month',
        'year': 'This Year'
    }
    
    return render_template('leaderboard.html', 
                         leaderboard=leaderboard,
                         current_user=current_user,
                         user=current_user,
                         selected_timeframe=timeframe_display[timeframe],
                         selected_metric=metric,
                         request=request)
