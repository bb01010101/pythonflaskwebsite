from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from .models import User, Entry, Message
from . import db, socketio
import json
import datetime
from flask_socketio import emit

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
            'water_intake': entry.water_intake,
            'running_mileage': entry.running_mileage
        }
        
        # Process weekly data
        week_str = entry.date.strftime('%Y-W%W')
        if week_str not in chart_data['weekly']:
            chart_data['weekly'][week_str] = {
                'sleep_hours': 0,
                'calories': 0,
                'water_intake': 0,
                'running_mileage': 0
            }
        chart_data['weekly'][week_str]['sleep_hours'] += entry.sleep_hours
        chart_data['weekly'][week_str]['calories'] += entry.calories
        chart_data['weekly'][week_str]['water_intake'] += entry.water_intake
        chart_data['weekly'][week_str]['running_mileage'] += entry.running_mileage
        
        # Process monthly data
        month_str = entry.date.strftime('%Y-%m')
        if month_str not in chart_data['monthly']:
            chart_data['monthly'][month_str] = {
                'sleep_hours': 0,
                'calories': 0,
                'water_intake': 0,
                'running_mileage': 0
            }
        chart_data['monthly'][month_str]['sleep_hours'] += entry.sleep_hours
        chart_data['monthly'][month_str]['calories'] += entry.calories
        chart_data['monthly'][month_str]['water_intake'] += entry.water_intake
        chart_data['monthly'][month_str]['running_mileage'] += entry.running_mileage
        
        # Process yearly data
        year_str = entry.date.strftime('%Y')
        if year_str not in chart_data['yearly']:
            chart_data['yearly'][year_str] = {
                'sleep_hours': 0,
                'calories': 0,
                'water_intake': 0,
                'running_mileage': 0
            }
        chart_data['yearly'][year_str]['sleep_hours'] += entry.sleep_hours
        chart_data['yearly'][year_str]['calories'] += entry.calories
        chart_data['yearly'][year_str]['water_intake'] += entry.water_intake
        chart_data['yearly'][year_str]['running_mileage'] += entry.running_mileage
    
    print(f"Chart data: {chart_data}")  # Debug print
    
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
        notes = request.form.get('notes')

        print(f"Adding entry for user {current_user.id} on date {date}")  # Debug print
        print(f"Data: sleep={sleep_hours}, calories={calories}, water={water_intake}, miles={running_mileage}")  # Debug print

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

@views.route('/message_board')
@login_required
def message_board():
    messages = Message.query.order_by(Message.timestamp.asc()).all()
    print(f"Found {len(messages)} messages")  # Debug print
    
    # Convert messages to JSON-serializable format
    serialized_messages = []
    for message in messages:
        serialized_messages.append({
            'id': message.id,
            'content': message.content,
            'user_id': message.user_id,
            'username': message.author.first_name,
            'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        })
        print(f"Serialized message: {serialized_messages[-1]}")  # Debug print
    
    return render_template('message_board.html', messages=serialized_messages, user=current_user)

@socketio.on('new_message')
def handle_message(data):
    print(f"Received message from user {current_user.id}: {data}")  # Debug print
    if not current_user.is_authenticated:
        print("User not authenticated")  # Debug print
        return
    
    try:
        message = Message(
            content=data['content'],
            user_id=current_user.id
        )
        db.session.add(message)
        db.session.commit()
        print(f"Saved message {message.id} to database")  # Debug print
        
        response_data = {
            'user_id': current_user.id,
            'username': current_user.first_name,
            'content': message.content,
            'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }
        print(f"Broadcasting message: {response_data}")  # Debug print
        emit('message', response_data, broadcast=True)
    except Exception as e:
        print(f"Error handling message: {e}")  # Debug print
        db.session.rollback()

