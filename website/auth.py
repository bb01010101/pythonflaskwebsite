from flask import Blueprint, render_template, request, flash, redirect, url_for
from .models import User, Entry
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
        
        # Map metric names to their database column names
        metric_mapping = {
            'running_mileage': 'running_mileage',
            'calories': 'calories',
            'water': 'water_intake',
            'sleep': 'sleep_hours',
            'screen_time': 'screen_time'
        }
        
        metric_units = {
            'running_mileage': 'miles',
            'calories': 'kcal',
            'water': 'ml',
            'sleep': 'hours',
            'screen_time': 'hours'
        }

        # Get the actual database column name
        db_column = metric_mapping[metric]

        # Determine the date range based on the selected timeframe
        today = datetime.date.today()
        if timeframe == 'day':
            start_date = today
        elif timeframe == 'week':
            start_date = today - datetime.timedelta(days=today.weekday())
        elif timeframe == 'month':
            start_date = today.replace(day=1)
        else:  # year
            start_date = today.replace(month=1, day=1)

        # Query to get all users with their total metric values for the specified timeframe
        query = db.session.query(
            User.id,
            User.username,
            func.coalesce(func.sum(getattr(Entry, db_column)), 0).label('total')
        ).outerjoin(
            Entry, User.id == Entry.user_id
        ).filter(
            Entry.date >= start_date,
            Entry.date <= today
        ).group_by(User.id, User.username)

        # Sort based on metric type
        if metric == 'screen_time':
            query = query.order_by(func.coalesce(func.sum(getattr(Entry, db_column)), 0).asc())
        else:
            query = query.order_by(func.coalesce(func.sum(getattr(Entry, db_column)), 0).desc())

        results = query.all()

        # Create leaderboard data
        leaderboard = []
        for result in results:
            score = float(result.total) if result.total is not None else 0
            leaderboard.append({
                'user_id': result.id,
                'username': result.username,
                'score': round(score, 2),
                'unit': metric_units[metric]
            })

        return render_template('leaderboard.html',
                               leaderboard=leaderboard,
                               current_user=current_user,
                               selected_timeframe=timeframe,
                               selected_metric=metric)

    except Exception as e:
        flash('Error loading leaderboard. Please try again.', category='error')
        return redirect(url_for('views.home'))