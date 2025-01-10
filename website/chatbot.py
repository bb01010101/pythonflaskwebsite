from datetime import datetime, timedelta
import random
from . import db
from .models import User, Entry, Goal, ChatMessage

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

        # Analyze different metrics
        analysis = []
        
        # Running analysis
        total_miles = sum(entry.running_mileage for entry in entries)
        avg_miles = total_miles / len(entries)
        if avg_miles > 0:
            analysis.append(f"You've run an average of {avg_miles:.1f} miles per day.")

        # Sleep analysis
        avg_sleep = sum(entry.sleep_hours for entry in entries) / len(entries)
        if avg_sleep < 7:
            analysis.append("You might want to get more sleep - aim for 7-9 hours per night.")
        elif avg_sleep >= 7:
            analysis.append("Great job maintaining healthy sleep habits!")

        # Water intake analysis
        avg_water = sum(entry.water_intake for entry in entries) / len(entries)
        if avg_water < 2000:
            analysis.append("Try to increase your water intake to at least 2000ml per day.")
        else:
            analysis.append("You're doing great with staying hydrated!")

        # Screen time analysis
        avg_screen = sum(entry.screen_time for entry in entries) / len(entries)
        if avg_screen > 4:
            analysis.append("Consider reducing your screen time for better well-being.")

        return "\n".join(analysis)

    def generate_daily_goals(self, user):
        """Generate personalized daily goals based on user's history and current goals"""
        goals = []
        
        # Get user's latest entry
        latest_entry = Entry.query.filter_by(user_id=user.id).order_by(Entry.date.desc()).first()
        
        if latest_entry:
            # Running goal
            if latest_entry.running_mileage < 3:
                goals.append("🏃‍♂️ Aim to run at least 3 miles today")
            else:
                goals.append(f"🏃‍♂️ Try to maintain or exceed your {latest_entry.running_mileage:.1f} miles run")

            # Sleep goal
            if latest_entry.sleep_hours < 7:
                goals.append("😴 Target 7-8 hours of sleep tonight")
            
            # Water intake goal
            if latest_entry.water_intake < 2000:
                goals.append("💧 Drink at least 2000ml of water today")
            
            # Screen time goal
            if latest_entry.screen_time > 4:
                goals.append("📱 Try to reduce screen time to under 4 hours")
        else:
            # Default goals for new users
            goals = [
                "🏃‍♂️ Start with a 1-mile run or 15-minute walk",
                "😴 Get 7-8 hours of sleep",
                "💧 Drink 2000ml of water",
                "📱 Keep screen time under 4 hours"
            ]

        return goals

    def generate_weekly_goals(self, user):
        """Generate personalized weekly goals based on user's progress"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        
        entries = Entry.query.filter(
            Entry.user_id == user.id,
            Entry.date >= start_date,
            Entry.date <= end_date
        ).all()

        weekly_goals = []
        
        if entries:
            # Calculate current weekly totals
            total_miles = sum(entry.running_mileage for entry in entries)
            avg_sleep = sum(entry.sleep_hours for entry in entries) / len(entries)
            
            # Set progressive goals
            weekly_goals = [
                f"🏃‍♂️ Run a total of {max(total_miles * 1.1, 10):.1f} miles this week",
                f"😴 Maintain an average of {max(avg_sleep, 7):.1f} hours of sleep",
                "💧 Hit your daily water intake goal at least 5 days",
                "📱 Have at least 2 days with less than 2 hours of screen time",
                "🎯 Log your activities every day this week"
            ]
        else:
            # Default weekly goals for new users
            weekly_goals = [
                "🏃‍♂️ Run a total of 5 miles this week",
                "😴 Get at least 7 hours of sleep each night",
                "💧 Drink 2000ml of water daily",
                "📱 Keep average screen time under 4 hours",
                "🎯 Log your activities for all 7 days"
            ]

        return weekly_goals

    def process_message(self, user, message_text):
        """Process user message and generate appropriate response"""
        message_text = message_text.lower()
        
        # Check for specific keywords and generate appropriate responses
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
            
        elif any(word in message_text for word in ['help', 'guide', 'how']):
            response = ("I can help you with:\n"
                       "- Setting daily and weekly goals\n"
                       "- Analyzing your progress\n"
                       "- Providing motivation\n"
                       "- Giving health and fitness tips\n\n"
                       "Just ask me about any of these topics!")
            
        else:
            response = ("I'm here to help you reach your health and fitness goals! "
                       "You can ask me about:\n"
                       "- Your goals\n"
                       "- Your progress\n"
                       "- Motivation\n"
                       "Or just tell me how you're doing today!")

        return response

chatbot = HealthChatbot() 