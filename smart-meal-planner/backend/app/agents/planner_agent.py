
import json
import os
from typing import List, Dict, Any
from sqlmodel import Session, select
from app.models.all_models import Product, Deal, Store, User
from app.core.config import settings
from app.agents.nutrition_agent import NutritionAgent
import requests
import random

class MealPlannerAgent:
    def __init__(self, session: Session):
        self.session = session
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.OPENROUTER_MODEL
        self.nutrition_agent = NutritionAgent()

    def get_available_deals(self) -> str:
        """Fetches active deals and formats them for the LLM prompt."""
        statement = select(Deal, Product, Store).join(Product).join(Store)
        results = self.session.exec(statement).all()

        deal_list = []
        for deal, product, store in results:
            deal_list.append(f"- {product.name} at {store.name}: ${deal.price} ({deal.discount_pct}% off)")

        # Randomly select a subset to avoid token limits if list is huge
        if len(deal_list) > 50:
             deal_list = random.sample(deal_list, 50)

        return "\n".join(deal_list)

    def generate_plan(self, user: User) -> Dict[str, Any]:
        """Generates a meal plan using OpenRouter or Mock fallback."""
        deals_context = self.get_available_deals()

        prompt = f"""
        You are a smart meal planner assistant. Create a 7-day meal plan (Breakfast, Lunch, Dinner) for a household of {user.household_size}.
        Dietary preferences: {user.dietary_preferences}.

        Available Deals (Prioritize these ingredients to save money):
        {deals_context}

        Requirements:
        1. Create 21 unique meals (no repeats for dinner).
        2. Ensure variety in protein sources (Chicken, Beef, Pork, Fish, Vegetarian).
        3. Include diverse cuisines (Italian, Asian, Mexican, etc.).
        4. Prioritize ingredients on sale.

        Output format must be valid JSON with this structure:
        {{
            "days": [
                {{
                    "day": 1,
                    "meals": [
                        {{ "type": "Breakfast", "name": "...", "ingredients": ["item1", "item2"] }},
                        {{ "type": "Lunch", "name": "...", "ingredients": ["item1", "item2"] }},
                        {{ "type": "Dinner", "name": "...", "ingredients": ["item1", "item2"] }}
                    ]
                }},
                ... (up to day 7)
            ],
            "shopping_list_summary": "Short text summary of key items to buy on sale"
        }}
        """

        if settings.USE_MOCK_AI or not self.api_key:
            print("Using Mock AI Response")
            return self._mock_response(user)

        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            response.raise_for_status()
            content = response.json()['choices'][0]['message']['content']

            # Clean up content if it contains markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            plan = json.loads(content)
            return self.nutrition_agent.validate_plan(plan)

        except Exception as e:
            print(f"AI Generation Failed: {e}. Falling back to mock.")
            return self._mock_response(user)

    def _mock_response(self, user: User) -> Dict[str, Any]:
        # Generate a semi-random 7-day plan
        days = []

        is_vegetarian = False
        is_vegan = False
        if user.dietary_preferences:
            prefs = user.dietary_preferences.lower()
            if "vegetarian" in prefs: is_vegetarian = True
            if "vegan" in prefs: is_vegan = True

        # Pool of meals
        breakfasts = [
            {"name": "Oatmeal with Berries", "ing": ["Oats", "Milk", "Berries"], "tags": ["veg", "vegan"]},
            {"name": "Scrambled Eggs & Toast", "ing": ["Eggs", "Bread", "Butter"], "tags": ["veg"]},
            {"name": "Yogurt Parfait", "ing": ["Yogurt", "Granola", "Honey"], "tags": ["veg"]},
            {"name": "Pancakes", "ing": ["Flour", "Milk", "Eggs", "Syrup"], "tags": ["veg"]},
            {"name": "Avocado Toast", "ing": ["Bread", "Avocado", "Salt"], "tags": ["veg", "vegan"]},
            {"name": "Cereal & Milk", "ing": ["Cereal", "Milk"], "tags": ["veg"]},
            {"name": "Tofu Scramble", "ing": ["Tofu", "Spinach", "Turmeric"], "tags": ["veg", "vegan"]}
        ]

        lunches = [
            {"name": "Chicken Caesar Salad", "ing": ["Romaine Lettuce", "Chicken Breast", "Croutons", "Caesar Dressing"], "tags": []},
            {"name": "Ham & Cheese Sandwich", "ing": ["Bread", "Ham", "Cheese"], "tags": []},
            {"name": "Vegetable Soup", "ing": ["Carrots", "Celery", "Onions", "Broth"], "tags": ["veg", "vegan"]},
            {"name": "Turkey Wrap", "ing": ["Tortilla", "Turkey", "Lettuce", "Mayo"], "tags": []},
            {"name": "Quinoa Salad", "ing": ["Quinoa", "Cucumber", "Tomatoes", "Feta"], "tags": ["veg"]},
            {"name": "Grilled Cheese", "ing": ["Bread", "Cheese", "Butter"], "tags": ["veg"]},
            {"name": "Hummus & Veggie Wrap", "ing": ["Tortilla", "Hummus", "Peppers", "Cucumber"], "tags": ["veg", "vegan"]}
        ]

        dinners = [
            {"name": "Spaghetti Bolognese", "ing": ["Pasta", "Ground Beef", "Tomato Sauce", "Onions"], "tags": []},
            {"name": "Chicken Stir Fry", "ing": ["Chicken Thighs", "Rice", "Broccoli", "Soy Sauce"], "tags": []},
            {"name": "Baked Salmon", "ing": ["Salmon Fillet", "Asparagus", "Potatoes"], "tags": []},
            {"name": "Pork Chops with Veggies", "ing": ["Pork Chops", "Carrots", "Green Beans"], "tags": []},
            {"name": "Beef Tacos", "ing": ["Ground Beef", "Tortillas", "Lettuce", "Cheese"], "tags": []},
            {"name": "Vegetarian Curry", "ing": ["Chickpeas", "Coconut Milk", "Spinach", "Rice"], "tags": ["veg", "vegan"]},
            {"name": "Roast Chicken", "ing": ["Whole Chicken", "Potatoes", "Carrots"], "tags": []},
            {"name": "Lentil Shepherd's Pie", "ing": ["Lentils", "Potatoes", "Carrots", "Peas"], "tags": ["veg", "vegan"]},
            {"name": "Stuffed Bell Peppers", "ing": ["Bell Peppers", "Rice", "Black Beans", "Corn"], "tags": ["veg", "vegan"]},
            {"name": "Eggplant Parmesan", "ing": ["Eggplant", "Tomato Sauce", "Mozzarella", "Breadcrumbs"], "tags": ["veg"]}
        ]

        # Filter based on preferences
        def filter_meals(meal_list):
            filtered = []
            for m in meal_list:
                if is_vegan:
                    if "vegan" in m["tags"]: filtered.append(m)
                elif is_vegetarian:
                    if "veg" in m["tags"]: filtered.append(m)
                else:
                    filtered.append(m)
            return filtered

        valid_breakfasts = filter_meals(breakfasts)
        valid_lunches = filter_meals(lunches)
        valid_dinners = filter_meals(dinners)

        # Fallback if too strict
        if not valid_dinners: valid_dinners = dinners

        # Shuffle dinners for variety
        random.shuffle(valid_dinners)

        for i in range(1, 8):
            # cycle through breakfasts/lunches
            bf = valid_breakfasts[(i-1) % len(valid_breakfasts)]
            lu = valid_lunches[(i-1) % len(valid_lunches)]
            dn = valid_dinners[(i-1) % len(valid_dinners)]

            day_plan = {
                "day": i,
                "meals": [
                    { "type": "Breakfast", "name": bf["name"], "ingredients": bf["ing"] },
                    { "type": "Lunch", "name": lu["name"], "ingredients": lu["ing"] },
                    { "type": "Dinner", "name": dn["name"], "ingredients": dn["ing"] }
                ]
            }
            days.append(day_plan)

        summary = "Based on your preferences, we found great deals on fresh ingredients."
        if is_vegetarian: summary += " Enjoy these meat-free savings!"
        elif is_vegan: summary += " Enjoy these plant-based savings!"
        else: summary += " Stock up on proteins currently on sale!"

        plan = {
            "days": days,
            "shopping_list_summary": summary
        }
        return self.nutrition_agent.validate_plan(plan)
