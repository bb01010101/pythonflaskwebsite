from flask import Blueprint, render_template, request, flash, jsonify
from flask_login import login_required, current_user
from .models import Note
from . import db
import json

views = Blueprint('views', __name__)

@views.route('/', methods=['GET', 'POST'])
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
            return render_template('add_entry.html', error="An entry for this date already exists.")

        # Add a new entry
        new_entry = Entry(
            date=date,
            sleep_hours=sleep_hours,
            calories=calories,
            hydration=hydration,
            running_mileage=running_mileage,
            notes=notes
        )
        db.session.add(new_entry)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('add_entry.html')

@views.route('/edit/<int:entry_id>', methods=['GET', 'POST'])
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
        return redirect(url_for('view_data'))

    return render_template('edit_entry.html', entry=entry)

@views.route('/delete/<int:entry_id>', methods=['GET'])
def delete_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()  # Commit deletion
    return redirect(url_for('view_data'))


    return render_template("home.html", user=current_user)

@views.route('/delete-note', methods=['POST'])
def delete_note():
    note = json.loads(request.data)
    noteId = note['note']
    note = Note.query.get(noteId)
    if note:
        if note.user_id == current_user.id:
            db.session.delete(note)
            db.session.commit()
            return jsonify({})

    return jsonify({})
