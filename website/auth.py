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
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user:
            if check_password_hash(user.password, password):
                flash('Login successful!', category='success')
                login_user(user, remember=True)
                return redirect(url_for('views.home'))
            else:
                flash('Incorrect password.', category='error')
        else:
            flash('Email does not exist.', category='error')

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
        first_name = request.form.get('firstName')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')

        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already exists.', category='error')
        elif len(email) < 4: 
            flash('Email must be greater than 3 characters.', category='error') 
        elif len(first_name) < 2:
            flash('First name must be greater than 1 character.', category='error')
        elif password1 != password2:
            flash('Passwords don\'t match.', category='error')
        elif len(password1) < 7:
            flash('Password must be at least 7 characters.', category='error')
        else:
            new_user = User(email=email, first_name=first_name, 
                password=generate_password_hash(password1, method='pbkdf2:sha256'))
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
        'sleep': Entry.sleep_hours
    }
    
    metric_units = {
        'running_mileage': 'miles',
        'calories': 'kcal',
        'water': 'ml',
        'sleep': 'hours'
    }
    
    # Query to get aggregated data for the leaderboard
    query = db.session.query(
        User.id.label('user_id'),
        User.first_name.label('username'),
        func.sum(metric_columns[metric]).label('score')
    ).join(Entry).filter(
        Entry.date >= start_date,
        Entry.date <= (end_date if timeframe != 'day' else today)
    ).group_by(User.id, User.first_name).order_by(
        func.sum(metric_columns[metric]).desc()
    )
    
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
