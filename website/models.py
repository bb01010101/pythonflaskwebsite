from . import db
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin 
from sqlalchemy.sql import func
import datetime


class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(10000))
    date = db.Column(db.DateTime(timezone=True), default=func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    first_name = db.Column(db.String(150))
    notes = db.relationship('Note')

# Database Model
class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=datetime.date.today)
    sleep_hours = db.Column(db.Float, nullable=False)
    calories = db.Column(db.Integer, nullable=False)
    hydration = db.Column(db.Float, nullable=False)  # Liters
    running_mileage = db.Column(db.Float, nullable=False)
    notes = db.Column(db.String, nullable=True)

