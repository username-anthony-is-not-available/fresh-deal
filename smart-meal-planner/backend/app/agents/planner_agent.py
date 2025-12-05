
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
        breakfasts = ["Oatmeal with Berries", "Scrambled Eggs & Toast", "Yogurt Parfait", "Pancakes", "Avocado Toast", "Cereal & Milk", "Breakfast Burrito"]
        lunches = ["Chicken Caesar Salad", "Ham & Cheese Sandwich", "Leftover Pasta", "Vegetable Soup", "Turkey Wrap", "Quinoa Salad", "Grilled Cheese"]
        dinners = [
            {"name": "Spaghetti Bolognese", "ing": ["Pasta", "Ground Beef", "Tomato Sauce", "Onions"]},
            {"name": "Chicken Stir Fry", "ing": ["Chicken Thighs", "Rice", "Broccoli", "Soy Sauce"]},
            {"name": "Baked Salmon", "ing": ["Salmon Fillet", "Asparagus", "Potatoes"]},
            {"name": "Pork Chops with Veggies", "ing": ["Pork Chops", "Carrots", "Green Beans"]},
            {"name": "Beef Tacos", "ing": ["Ground Beef", "Tortillas", "Lettuce", "Cheese"]},
            {"name": "Vegetarian Curry", "ing": ["Chickpeas", "Coconut Milk", "Spinach", "Rice"]},
            {"name": "Roast Chicken", "ing": ["Whole Chicken", "Potatoes", "Carrots"]}
        ]

        # Shuffle dinners for variety
        random.shuffle(dinners)

        for i in range(1, 8):
            day_plan = {
                "day": i,
                "meals": [
                    { "type": "Breakfast", "name": breakfasts[(i-1) % 7], "ingredients": ["Eggs", "Bread"] if "Eggs" in breakfasts[(i-1)%7] else ["Oats", "Milk"] },
                    { "type": "Lunch", "name": lunches[(i-1) % 7], "ingredients": ["Bread", "Ham"] if "Sandwich" in lunches[(i-1)%7] else ["Chicken", "Lettuce"] },
                    { "type": "Dinner", "name": dinners[i-1]["name"], "ingredients": dinners[i-1]["ing"] }
                ]
            }
            days.append(day_plan)

        plan = {
            "days": days,
            "shopping_list_summary": "Buy Chicken, Ground Beef, and Salmon on sale. Stock up on Rice and Pasta."
        }
        return self.nutrition_agent.validate_plan(plan)
