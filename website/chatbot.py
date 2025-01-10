from datetime import datetime, timedelta
import random
from . import db
from .models import User, Entry, Goal, ChatMessage
import openai
import os

class HealthChatbot:
    def __init__(self):
        self.motivation_quotes = [
            "Every step forward is progress, no matter how small.",
            "Your only competition is yourself yesterday.",
            "Success is built one habit at a time.",
            "Small daily improvements lead to stunning results.",
            "The journey of a thousand miles begins with a single step.",
            "You don't have to be extreme, just consistent.",
            "Progress takes patience and persistence.",
            "Focus on the progress, not the perfection.",
            "Every day is a new opportunity to improve.",
            "Your future self will thank you for the efforts you make today."
        ]
        # Initialize OpenAI client
        openai.api_key = os.environ.get('OPENAI_API_KEY')

    def get_random_motivation(self):
        """Return a random motivational quote"""
        return random.choice(self.motivation_quotes)

    def analyze_progress(self, user, days=7):
        """Analyze user's progress over the specified number of days"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        entries = Entry.query.filter(
            Entry.user_id == user.id,
            Entry.date >= start_date,
            Entry.date <= end_date
        ).all()

        if not entries:
            return "I don't have enough data to analyze your progress yet. Start by logging your daily activities!"

        # Prepare data for analysis
        metrics = {
            'running_mileage': [],
            'sleep_hours': [],
            'water_intake': [],
            'screen_time': [],
            'calories': []
        }
        
        for entry in entries:
            metrics['running_mileage'].append(entry.running_mileage)
            metrics['sleep_hours'].append(entry.sleep_hours)
            metrics['water_intake'].append(entry.water_intake)
            metrics['screen_time'].append(entry.screen_time)
            metrics['calories'].append(entry.calories)

        # Create a prompt for OpenAI
        prompt = f"""As a health and fitness coach, analyze this user's data for the past {days} days:

Running: {metrics['running_mileage']} miles per day
Sleep: {metrics['sleep_hours']} hours per day
Water Intake: {metrics['water_intake']} ml per day
Screen Time: {metrics['screen_time']} hours per day
Calories: {metrics['calories']} per day

Provide a brief, encouraging analysis of their progress and specific recommendations for improvement. Focus on positive trends and actionable advice."""

        try:
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a supportive and knowledgeable health coach. Keep responses concise and actionable."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=250,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            # Fallback to basic analysis if OpenAI fails
            analysis = []
            avg_miles = sum(metrics['running_mileage']) / len(entries)
            avg_sleep = sum(metrics['sleep_hours']) / len(entries)
            avg_water = sum(metrics['water_intake']) / len(entries)
            avg_screen = sum(metrics['screen_time']) / len(entries)

            if avg_miles > 0:
                analysis.append(f"You've run an average of {avg_miles:.1f} miles per day.")
            if avg_sleep < 7:
                analysis.append("Try to get more sleep - aim for 7-9 hours per night.")
            elif avg_sleep >= 7:
                analysis.append("Great job maintaining healthy sleep habits!")
            if avg_water < 2000:
                analysis.append("Try to increase your water intake to at least 2000ml per day.")
            if avg_screen > 4:
                analysis.append("Consider reducing your screen time for better well-being.")

            return "\n".join(analysis)

    def generate_daily_goals(self, user):
        """Generate personalized daily goals based on user's history and current goals"""
        latest_entry = Entry.query.filter_by(user_id=user.id).order_by(Entry.date.desc()).first()
        
        # Prepare context for OpenAI
        context = {
            'latest_entry': {
                'running_mileage': latest_entry.running_mileage if latest_entry else 0,
                'sleep_hours': latest_entry.sleep_hours if latest_entry else 0,
                'water_intake': latest_entry.water_intake if latest_entry else 0,
                'screen_time': latest_entry.screen_time if latest_entry else 0,
                'calories': latest_entry.calories if latest_entry else 0
            } if latest_entry else None
        }

        prompt = f"""As a health coach, generate 4-5 specific, achievable daily goals for this user.
Current metrics:
{context}

Goals should be motivating and slightly challenging but attainable. Include emojis for each goal."""

        try:
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a supportive health coach. Generate specific, actionable daily goals. Use emojis and keep each goal concise."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.7
            )
            goals = response.choices[0].message.content.split('\n')
            return [goal for goal in goals if goal.strip()]
        except Exception as e:
            # Fallback to basic goals if OpenAI fails
            if latest_entry:
                return [
                    f"🏃‍♂️ Aim to run {max(latest_entry.running_mileage + 0.5, 3)} miles today",
                    "😴 Get 7-8 hours of sleep tonight",
                    "💧 Drink at least 2000ml of water",
                    "📱 Keep screen time under 4 hours",
                    "🎯 Log all your activities today"
                ]
            else:
                return [
                    "🏃‍♂️ Start with a 1-mile run or 15-minute walk",
                    "😴 Get 7-8 hours of sleep",
                    "💧 Drink 2000ml of water",
                    "📱 Keep screen time under 4 hours",
                    "🎯 Log your activities today"
                ]

    def generate_weekly_goals(self, user):
        """Generate personalized weekly goals based on user's progress"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        
        entries = Entry.query.filter(
            Entry.user_id == user.id,
            Entry.date >= start_date,
            Entry.date <= end_date
        ).all()

        # Prepare context for OpenAI
        metrics = {
            'total_miles': sum(entry.running_mileage for entry in entries) if entries else 0,
            'avg_sleep': sum(entry.sleep_hours for entry in entries) / len(entries) if entries else 0,
            'avg_water': sum(entry.water_intake for entry in entries) / len(entries) if entries else 0,
            'avg_screen': sum(entry.screen_time for entry in entries) / len(entries) if entries else 0
        }

        prompt = f"""As a health coach, generate 4-5 specific weekly goals based on the user's current metrics:
Last week's performance:
- Total running: {metrics['total_miles']:.1f} miles
- Average sleep: {metrics['avg_sleep']:.1f} hours
- Average water intake: {metrics['avg_water']:.0f} ml
- Average screen time: {metrics['avg_screen']:.1f} hours

Goals should be challenging but achievable. Include emojis and make them specific."""

        try:
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a supportive health coach. Generate specific, actionable weekly goals. Use emojis and keep each goal concise."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.7
            )
            goals = response.choices[0].message.content.split('\n')
            return [goal for goal in goals if goal.strip()]
        except Exception as e:
            # Fallback to basic weekly goals if OpenAI fails
            if entries:
                return [
                    f"🏃‍♂️ Run a total of {max(metrics['total_miles'] * 1.1, 10):.1f} miles this week",
                    f"😴 Maintain an average of {max(metrics['avg_sleep'], 7):.1f} hours of sleep",
                    "💧 Hit your daily water intake goal at least 5 days",
                    "📱 Have at least 2 days with less than 2 hours of screen time",
                    "🎯 Log your activities every day this week"
                ]
            else:
                return [
                    "🏃‍♂️ Run a total of 5 miles this week",
                    "😴 Get at least 7 hours of sleep each night",
                    "💧 Drink 2000ml of water daily",
                    "📱 Keep average screen time under 4 hours",
                    "🎯 Log your activities for all 7 days"
                ]

    def process_message(self, user, message_text):
        """Process user message and generate appropriate response using OpenAI"""
        # Get user's recent entries for context
        recent_entries = Entry.query.filter_by(user_id=user.id).order_by(Entry.date.desc()).limit(7).all()
        
        # Prepare context about the user's recent activity
        context = ""
        if recent_entries:
            context = "Recent activity:\n"
            for entry in recent_entries[:3]:
                context += f"- {entry.date}: {entry.running_mileage} miles run, {entry.sleep_hours}h sleep, {entry.water_intake}ml water\n"

        try:
            # Generate response using OpenAI
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": """You are a supportive and knowledgeable AI health coach. 
Your goal is to help users achieve their fitness goals and maintain healthy habits.
Keep responses concise, positive, and actionable.
When appropriate, include specific references to the user's data.
Use emojis to make responses engaging."""},
                    {"role": "user", "content": f"User context:\n{context}\n\nUser message: {message_text}"}
                ],
                max_tokens=300,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            # Fallback to basic responses if OpenAI fails
            message_text = message_text.lower()
            if any(word in message_text for word in ['goal', 'goals', 'target']):
                daily_goals = self.generate_daily_goals(user)
                weekly_goals = self.generate_weekly_goals(user)
                response = "Here are your personalized goals:\n\nDaily Goals:\n"
                response += "\n".join(daily_goals)
                response += "\n\nWeekly Goals:\n"
                response += "\n".join(weekly_goals)
            elif any(word in message_text for word in ['progress', 'doing', 'analysis']):
                response = self.analyze_progress(user)
            elif any(word in message_text for word in ['motivate', 'motivation', 'inspire']):
                response = self.get_random_motivation()
            else:
                response = ("I'm here to help you reach your health and fitness goals! "
                          "You can ask me about:\n"
                          "- Your goals\n"
                          "- Your progress\n"
                          "- Motivation\n"
                          "Or just tell me how you're doing today!")
            return response

chatbot = HealthChatbot() 