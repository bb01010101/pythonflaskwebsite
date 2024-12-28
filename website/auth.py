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
            login_id = request.form.get('email')  # This will now be either email or username
            password = request.form.get('password')

            logger.info(f"Login attempt for: {login_id}")

            # Try to find user by email first, then by username if not found
            user = User.query.filter_by(email=login_id).first()
            if not user:
                user = User.query.filter_by(username=login_id).first()

            if user:
                try:
                    if check_password_hash(user.password, password):
                        login_user(user, remember=True)
                        logger.info(f"Successful login for user: {user.username}")
                        flash('Login successful!', category='success')
                        return redirect(url_for('views.home'))
                    else:
                        logger.info(f"Incorrect password for user: {user.username}")
                        flash('Incorrect password.', category='error')
                except Exception as e:
                    logger.error(f"Error checking password: {str(e)}", exc_info=True)
                    flash('An error occurred during login. Please try again.', category='error')
            else:
                logger.info(f"No user found for login_id: {login_id}")
                flash('Email or username not found.', category='error')

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