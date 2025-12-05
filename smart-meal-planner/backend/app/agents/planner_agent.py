
import json
import os
from typing import List, Dict, Any
from sqlmodel import Session, select
from app.models.all_models import Product, Deal, Store, User
from app.core.config import settings
import requests

class MealPlannerAgent:
    def __init__(self, session: Session):
        self.session = session
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.OPENROUTER_MODEL

    def get_available_deals(self) -> str:
        """Fetches active deals and formats them for the LLM prompt."""
        statement = select(Deal, Product, Store).join(Product).join(Store)
        results = self.session.exec(statement).all()

        deal_list = []
        for deal, product, store in results:
            deal_list.append(f"- {product.name} at {store.name}: ${deal.price} ({deal.discount_pct}% off)")

        return "\n".join(deal_list)

    def generate_plan(self, user: User) -> Dict[str, Any]:
        """Generates a meal plan using OpenRouter or Mock fallback."""
        deals_context = self.get_available_deals()

        prompt = f"""
        You are a smart meal planner assistant. Create a 3-day meal plan (Breakfast, Lunch, Dinner) for a household of {user.household_size}.
        Dietary preferences: {user.dietary_preferences}.

        Available Deals (Prioritize these ingredients to save money):
        {deals_context}

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
                ...
            ],
            "shopping_list_summary": "Short text summary of key items"
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
            # Basic parsing of JSON from markdown block if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            return json.loads(content)

        except Exception as e:
            print(f"AI Generation Failed: {e}. Falling back to mock.")
            return self._mock_response(user)

    def _mock_response(self, user: User) -> Dict[str, Any]:
        return {
            "days": [
                {
                    "day": 1,
                    "meals": [
                        { "type": "Breakfast", "name": "Oatmeal with Bananas", "ingredients": ["Oats", "Bananas", "Milk"] },
                        { "type": "Lunch", "name": "Chicken Salad", "ingredients": ["Chicken Thighs", "Spinach", "Tomatoes"] },
                        { "type": "Dinner", "name": "Spaghetti Bolognese", "ingredients": ["Pasta", "Ground Beef", "Tomato Sauce"] }
                    ]
                },
                {
                    "day": 2,
                    "meals": [
                        { "type": "Breakfast", "name": "Scrambled Eggs & Toast", "ingredients": ["Eggs", "Bread", "Butter"] },
                        { "type": "Lunch", "name": "Leftover Pasta", "ingredients": ["Pasta"] },
                        { "type": "Dinner", "name": "Pork Chops & Potatoes", "ingredients": ["Pork Chops", "Potatoes", "Carrots"] }
                    ]
                },
                {
                    "day": 3,
                    "meals": [
                        { "type": "Breakfast", "name": "Yogurt & Fruit", "ingredients": ["Yogurt", "Apples"] },
                        { "type": "Lunch", "name": "Ham Sandwich", "ingredients": ["Bread", "Ham", "Cheese"] },
                        { "type": "Dinner", "name": "Vegetable Stir Fry", "ingredients": ["Rice", "Broccoli", "Onions", "Carrots"] }
                    ]
                }
            ],
            "shopping_list_summary": "Based on the plan, buy Chicken, Ground Beef, Pork Chops on sale."
        }
