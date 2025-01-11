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
        
        # System message that defines the chatbot's personality and capabilities
        self.system_message = """You are an expert AI health and fitness coach with deep knowledge in:
- Exercise physiology and training principles
- Nutrition and dietary planning
- Sleep optimization and recovery
- Mental wellness and motivation
- Habit formation and behavior change

Your personality traits:
- Supportive and encouraging, but also direct when needed
- Data-driven, making recommendations based on user metrics
- Holistic in approach, considering all aspects of health
- Engaging and conversational, using emojis appropriately
- Professional but friendly

When responding:
1. Format responses in clear paragraphs or bullet points
2. Use markdown for emphasis when appropriate
3. Include relevant emojis to make the conversation engaging
4. Reference user's data when available
5. Provide specific, actionable advice
6. Keep responses concise but informative
7. Always maintain a positive, motivating tone

You have access to user's:
- Daily activity metrics (running, sleep, water intake, etc.)
- Historical progress data
- Goals and preferences

Focus on helping users build sustainable healthy habits and achieve their fitness goals."""

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
        try:
            # Get user's recent entries and chat history for context
            recent_entries = Entry.query.filter_by(user_id=user.id).order_by(Entry.date.desc()).limit(7).all()
            recent_messages = ChatMessage.query.filter_by(user_id=user.id).order_by(ChatMessage.timestamp.desc()).limit(10).all()
            
            # Prepare detailed context about the user's recent activity
            context = self._prepare_user_context(user, recent_entries)
            
            # Prepare conversation history
            messages = [{"role": "system", "content": self.system_message}]
            
            # Add recent conversation history (in reverse to get correct order)
            for msg in reversed(recent_messages):
                role = "assistant" if msg.is_bot else "user"
                messages.append({"role": role, "content": msg.content})
            
            # Add current message with enhanced context
            messages.append({
                "role": "user", 
                "content": f"{context}\n\nUser message: {message_text}"
            })

            # Generate response using OpenAI with enhanced parameters
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.8,  # Slightly increased for more creativity
                max_tokens=800,   # Increased for more detailed responses
                presence_penalty=0.6,  # Encourage more varied responses
                frequency_penalty=0.4,  # Reduce repetition
                top_p=0.9,  # More focused but still creative responses
            )
            return response.choices[0].message.content

        except Exception as e:
            # Log the error for debugging
            print(f"Error in process_message: {str(e)}")
            # Return a more natural fallback response
            return self._generate_fallback_response(message_text, user)

    def _prepare_user_context(self, user, recent_entries):
        """Prepare detailed context about the user's activity and progress"""
        context = "User Context:\n"
        
        if recent_entries:
            # Add recent activity summary
            context += "\nRecent Activity:\n"
            for entry in recent_entries[:3]:
                context += f"- Date: {entry.date}\n"
                context += f"  • Running: {entry.running_mileage} miles\n"
                context += f"  • Sleep: {entry.sleep_hours} hours\n"
                context += f"  • Water: {entry.water_intake}ml\n"
                context += f"  • Calories: {entry.calories}\n"
                if entry.notes:
                    context += f"  • Notes: {entry.notes}\n"
            
            # Calculate trends
            avg_running = sum(e.running_mileage for e in recent_entries) / len(recent_entries)
            avg_sleep = sum(e.sleep_hours for e in recent_entries) / len(recent_entries)
            avg_water = sum(e.water_intake for e in recent_entries) / len(recent_entries)
            
            context += "\nWeekly Averages:\n"
            context += f"• Average daily running: {avg_running:.1f} miles\n"
            context += f"• Average sleep: {avg_sleep:.1f} hours\n"
            context += f"• Average water intake: {avg_water:.0f}ml\n"
            
            # Add trend analysis
            running_trend = [e.running_mileage for e in recent_entries]
            if len(running_trend) > 1:
                if running_trend[0] > running_trend[-1]:
                    context += "\nTrends: Running distance has been increasing\n"
                elif running_trend[0] < running_trend[-1]:
                    context += "\nTrends: Running distance has been decreasing\n"
        else:
            context += "\nNo recent activity data available. This appears to be a new user.\n"
        
        # Add user's goals if any
        goals = Goal.query.filter_by(user_id=user.id, completed=False).all()
        if goals:
            context += "\nActive Goals:\n"
            for goal in goals:
                context += f"• {goal.description} (Target: {goal.target_value} {goal.metric_type})\n"
        
        return context

    def _generate_fallback_response(self, message_text, user):
        """Generate a more natural fallback response based on the message content"""
        message_lower = message_text.lower()
        
        if 'workout' in message_lower or 'exercise' in message_lower:
            return """💪 Here are some personalized workout recommendations:

1. **Cardio Focus**
• Start with a 5-minute warm-up
• 20-30 minutes of moderate-intensity running or cycling
• Cool down with 5 minutes of walking

2. **Strength Training**
• Bodyweight exercises: push-ups, squats, lunges
• 3 sets of 10-12 repetitions
• Rest 60 seconds between sets

Remember to:
• Stay hydrated
• Listen to your body
• Maintain proper form

Would you like more specific exercises or a detailed workout plan?"""

        elif 'nutrition' in message_lower or 'diet' in message_lower or 'food' in message_lower:
            return """🥗 Here are some key nutrition tips:

1. **Balanced Meals**
• Include protein, complex carbs, and healthy fats
• Aim for colorful vegetables
• Control portion sizes

2. **Hydration**
• Drink water throughout the day
• Monitor your intake
• Limit sugary drinks

3. **Timing**
• Eat regular meals
• Plan pre and post-workout nutrition
• Listen to hunger cues

Would you like specific meal suggestions or a nutrition plan?"""

        elif 'sleep' in message_lower or 'rest' in message_lower:
            return """😴 Here are some sleep optimization tips:

1. **Evening Routine**
• Consistent bedtime
• Dim lights 1-2 hours before bed
• Limit screen time

2. **Environment**
• Cool, dark room
• Comfortable bedding
• Minimize noise

3. **Habits**
• Avoid caffeine after 2 PM
• Regular exercise (but not too close to bedtime)
• Relaxation techniques

Would you like more specific advice for better sleep quality?"""

        else:
            return """I'm here to help you with your health and fitness journey! Let's focus on what matters most to you:

• 🎯 Setting achievable goals
• 💪 Personalized workout plans
• 🥗 Nutrition guidance
• 😴 Sleep optimization
• 📊 Progress tracking
• 🎉 Staying motivated

What specific aspect would you like to discuss?"""

chatbot = HealthChatbot() 