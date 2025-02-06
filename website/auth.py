from flask import Blueprint, render_template, request, flash, redirect, url_for
from .models import User, Entry
from werkzeug.security import generate_password_hash, check_password_hash
from . import db
from flask_login import login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)

auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')

            logger.info(f"Login attempt for: {email}")

            user = User.query.filter_by(email=email).first()
            if user:
                if check_password_hash(user.password, password):
                    logger.info(f"Successful login for user: {user.username}")
                    flash('Logged in successfully!', category='success')
                    login_user(user, remember=True)
                    
                    # Trigger Strava sync if needed
                    user.sync_strava_if_needed()
                    
                    return redirect(url_for('views.home'))
                else:
                    logger.info(f"Incorrect password for user: {user.username}")
                    flash('Incorrect password, try again.', category='error')
            else:
                logger.info(f"No user found for email: {email}")
                flash('Email does not exist.', category='error')

        return render_template("login.html", user=current_user)
    except Exception as e:
        logger.error(f"Unexpected error in login route: {str(e)}", exc_info=True)
        flash('An unexpected error occurred. Please try again.', category='error')
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