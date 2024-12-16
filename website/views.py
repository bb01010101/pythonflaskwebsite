from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from .models import User, Entry
from . import db
import json
import datetime

views = Blueprint('views', __name__)


@views.route('/', methods=['GET', 'POST'])
@login_required
def home():
    return render_template("index.html", user=current_user)

@views.route('/view_charts', methods=['GET', 'POST'])
@login_required
def view_charts():
    entries = Entry.query.filter_by(user_id=current_user.id).order_by(Entry.date.asc()).all()
    
    # Prepare data for charts
    chart_data = {
        'daily': {},
        'weekly': {},
        'monthly': {},
        'yearly': {}
    }
    
    # Process daily data
    for entry in entries:
        date_str = entry.date.strftime('%Y-%m-%d')
        chart_data['daily'][date_str] = {
            'sleep_hours': entry.sleep_hours,
            'calories': entry.calories,
            'hydration': entry.hydration,
            'running_mileage': entry.running_mileage
        }
    
    return render_template("view_charts.html", user=current_user, chart_data=chart_data)

@views.route('/view_data', methods=['GET', 'POST'])
@login_required
def view_data():
    entries = Entry.query.filter_by(user_id=current_user.id).order_by(Entry.date.desc()).all()
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
        hydration = float(request.form.get('hydration'))
        running_mileage = float(request.form.get('running_mileage'))
        notes = request.form.get('notes')

        # Check if an entry for this date already exists
        existing_entry = Entry.query.filter_by(date=date).first()
        if existing_entry:
           # Update the existing entry instead of creating a new one
            existing_entry.sleep_hours = sleep_hours
            existing_entry.calories = calories
            existing_entry.hydration = hydration
            existing_entry.running_mileage = running_mileage
            existing_entry.notes = notes
            db.session.commit()
            flash('Entry updated successfully!', category='success')
            return redirect(url_for('views.view_data'))
        # Add a new entry
        new_entry = Entry(
            date=date,
            sleep_hours=sleep_hours,
            calories=calories,
            hydration=hydration,
            running_mileage=running_mileage,
            notes=notes,
            user_id=current_user.id
        )
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
        entry.hydration = float(request.form['hydration'])
        entry.running_mileage = float(request.form['running_mileage'])
        entry.notes = request.form['notes']
        
        db.session.commit()  # Save the changes
        return redirect(url_for('views.view_data'))

    return render_template('edit_entry.html', entry=entry, user=current_user)

@views.route('/delete/<int:entry_id>', methods=['GET'])
@login_required
def delete_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()  # Commit deletion
    return redirect(url_for('views.view_data'))

