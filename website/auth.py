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
    try:
        metric = request.args.get('metric', 'running_mileage')
        timeframe = request.args.get('timeframe', 'day')
        
        # Calculate the date range based on timeframe
        today = datetime.now().date()
        if timeframe == 'day':
            start_date = today
            end_date = today
            timeframe_display = 'Today'
        elif timeframe == 'week':
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)
            timeframe_display = 'This Week'
        elif timeframe == 'month':
            start_date = today.replace(day=1)
            if today.month == 12:
                end_date = today.replace(day=31)
            else:
                end_date = (today.replace(day=1, month=today.month + 1) - timedelta(days=1))
            timeframe_display = 'This Month'
        else:  # year
            start_date = today.replace(month=1, day=1)
            end_date = today.replace(month=12, day=31)
            timeframe_display = 'This Year'

        print(f"Date range: {start_date} to {end_date}")  # Debug log
        
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

        # First, get all users
        users = User.query.all()
        print(f"Found {len(users)} users")  # Debug log

        # Then, for each user, get their metric sum for the time period
        leaderboard_data = []
        for user in users:
            entries = Entry.query.filter(
                Entry.user_id == user.id,
                Entry.date >= start_date,
                Entry.date <= end_date
            ).all()
            
            # Calculate total score for the metric
            total_score = 0
            for entry in entries:
                value = getattr(entry, metric)
                if value is not None:
                    total_score += value
            
            leaderboard_data.append({
                'user_id': user.id,
                'username': user.username,
                'score': round(total_score, 2),
                'unit': metric_units[metric]
            })

        print(f"Processed {len(leaderboard_data)} entries for leaderboard")  # Debug log

        # Sort the leaderboard
        if metric == 'screen_time':
            leaderboard_data.sort(key=lambda x: x['score'])
        else:
            leaderboard_data.sort(key=lambda x: x['score'], reverse=True)

        return render_template('leaderboard.html',
                             leaderboard=leaderboard_data,
                             current_user=current_user,
                             user=current_user,
                             selected_timeframe=timeframe_display,
                             selected_metric=metric,
                             request=request)
                             
    except Exception as e:
        print(f"Error in leaderboard route: {str(e)}")  # Debug log
        import traceback
        traceback.print_exc()  # Print full error traceback
        flash('Error loading leaderboard. Please try again.', category='error')
        return redirect(url_for('views.home'))
