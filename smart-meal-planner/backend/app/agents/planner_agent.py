
import json
import os
import random
import logging
import requests
from typing import List, Dict, Any
from sqlmodel import Session, select
from app.models.all_models import Product, Deal, Store, User
from app.core.config import settings
from app.agents.nutrition_agent import NutritionAgent
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

class MealPlannerAgent:
    def __init__(self, session: Session):
        self.session = session
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.OPENROUTER_MODEL
        self.nutrition_agent = NutritionAgent()
        self.recipes = self._load_recipes()
        self.llm_service = LLMService()

    def _load_recipes(self) -> List[Dict]:
        try:
            # Adjust path relative to where app is run
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            file_path = os.path.join(base_path, "data", "recipes.json")
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading recipes: {e}")
            return []

    def get_available_deals(self) -> List[Dict]:
        """Fetches active deals."""
        statement = select(Deal, Product, Store).join(Product).join(Store)
        results = self.session.exec(statement).all()

        deals_data = []
        for deal, product, store in results:
            if deal.discount_pct > 0: # Only care about actual sales
                deals_data.append({
                    "product": product.name,
                    "store": store.name,
                    "price": deal.price,
                    "discount": deal.discount_pct,
                    "category": product.category, # Ensure category is available if possible, else might be None
                    "unit": product.unit_type # Use unit_type from Product model
                })
        return deals_data

    def generate_plan(self, user: User) -> Dict[str, Any]:
        """Generates a meal plan using LLM Service."""

        deals = self.get_available_deals()

        user_prefs = {
            "household_size": user.household_size,
            "dietary_preferences": user.dietary_preferences,
            "postal_code": user.postal_code
        }

        try:
            # Try LLM generation first
            plan = self.llm_service.generate_meal_plan(user_prefs, deals, self.recipes)
            validated_plan = self._validate_and_enrich(plan)
            return validated_plan
        except Exception as e:
            logger.error(f"LLM generation failed or validation failed: {e}. Falling back to heuristic plan.")
            return self._generate_structured_plan(user)

    def _validate_and_enrich(self, plan: Dict) -> Dict:
        """
        Validates LLM output and adds missing data (ingredients, nutrition) from local DB.
        """
        # Create a lookup map for recipes
        recipe_map = {r["id"]: r for r in self.recipes}

        if "meal_plan" not in plan:
             # If the LLM returned the old structure or something else, try to adapt or fail
             if "days" in plan:
                 # It might be the mock fallback format which uses 'days' key but structured differently
                 # Actually LLMService._generate_mock_plan now uses 'meal_plan' key too.
                 # So if we are here, something is wrong.
                 pass
             raise ValueError("Invalid plan structure from LLM")

        enriched_days = []

        for day in plan["meal_plan"]:
            enriched_day = {
                "day": day["day"],
                "day_name": day.get("day_name", ""),
                "date": day.get("date", ""),
                "meals": [] # We will flatten to array for compatibility with some parts, or keep structure?
                            # The frontend expects `days` array where each day has `meals` array.
                            # But the new requirement asked for `breakfast`, `lunch`, `dinner` keys in JSON.
                            # However, to maintain compatibility with Frontend components (MealCard), we might need to adapt.
                            # Wait, the plan says "Update Frontend ... Adapt to the new JSON structure".
                            # So we should keep the structure returned by LLMService, but ensure data is complete.
            }

            # We will keep the structure: day has 'breakfast', 'lunch', 'dinner' objects.
            # But we also need to make sure the frontend can handle it.
            # The user instruction says: "Adapt to the new JSON structure (`plan.meal_plan` array instead of `plan.days`)."
            # So I will return the plan as is, just enriched.

            for meal_type in ["breakfast", "lunch", "dinner"]:
                meal_info = day.get(meal_type)
                if not meal_info:
                    continue

                recipe_id = meal_info.get("recipe_id")
                recipe_details = recipe_map.get(recipe_id)

                if not recipe_details:
                    # Fallback if ID is invalid or missing
                    # We could try to match by name or pick a random one?
                    # For safety, pick a random one of same type
                    candidates = [r for r in self.recipes if r["meal_type"].lower() == meal_type.lower()]
                    if candidates:
                        recipe_details = random.choice(candidates)
                        meal_info["recipe_id"] = recipe_details["id"]
                        meal_info["recipe_name"] = recipe_details["name"]
                        meal_info["reason"] += " (Fallback selection)"

                if recipe_details:
                    # Enrich with ingredients and nutrition
                    meal_info["ingredients"] = recipe_details["ingredients"] # List of objects {item, quantity, unit}
                    meal_info["nutrition"] = recipe_details["nutrition"]
                    meal_info["instructions"] = recipe_details["instructions"]
                    meal_info["tags"] = recipe_details.get("tags", [])
                    meal_info["image"] = recipe_details.get("image", "/placeholder.jpg") # if we had images

            enriched_days.append(day)

        plan["meal_plan"] = enriched_days
        return plan

    def _generate_structured_plan(self, user: User) -> Dict[str, Any]:
        """
        Fallback heuristic plan generation.
        Matches the NEW structure but generated algorithmically.
        """
        deals = self.get_available_deals()
        deal_products = set(d["product"] for d in deals)

        # Helper to get dynamic dates
        week_dates = self.llm_service.get_next_week_dates()

        # Filter recipes based on dietary prefs
        is_vegetarian = False
        is_vegan = False
        if user.dietary_preferences:
            prefs = user.dietary_preferences.lower()
            if "vegetarian" in prefs: is_vegetarian = True
            if "vegan" in prefs: is_vegan = True

        suitable_recipes = []
        for r in self.recipes:
            if is_vegan:
                if "vegan" in r.get("tags", []): suitable_recipes.append(r)
            elif is_vegetarian:
                if "vegetarian" in r.get("tags", []) or "vegan" in r.get("tags", []): suitable_recipes.append(r)
            else:
                suitable_recipes.append(r)

        # Score recipes
        recipe_scores = []
        for r in suitable_recipes:
            score = 0
            for ing in r["ingredients"]:
                for dp in deal_products:
                    if ing["item"] in dp or dp in ing["item"]:
                        score += 1
            recipe_scores.append((score, r))

        recipe_scores.sort(key=lambda x: x[0], reverse=True)

        # Separate by meal type
        breakfasts = [r for s,r in recipe_scores if r["meal_type"] == "Breakfast"]
        lunches = [r for s,r in recipe_scores if r["meal_type"] == "Lunch"]
        dinners = [r for s,r in recipe_scores if r["meal_type"] == "Dinner"]

        # Ensure enough recipes
        if not breakfasts: breakfasts = [r for r in self.recipes if r["meal_type"] == "Breakfast"]
        if not lunches: lunches = [r for r in self.recipes if r["meal_type"] == "Lunch"]
        if not dinners: dinners = [r for r in self.recipes if r["meal_type"] == "Dinner"]

        days = []
        used_dinner_names = set()

        for i in range(7):
            date_info = week_dates[i]

            # Select unique dinner
            dinner = next((d for d in dinners if d["name"] not in used_dinner_names), random.choice(dinners))
            used_dinner_names.add(dinner["name"])

            bf = breakfasts[i % len(breakfasts)]
            lu = lunches[i % len(lunches)]

            days.append({
                "day": i + 1,
                "day_name": date_info["day_name"],
                "date": date_info["date"],
                "breakfast": {
                    "recipe_id": bf["id"],
                    "recipe_name": bf["name"],
                    "reason": "Heuristic selection",
                    "servings": user.household_size,
                    "ingredients": bf["ingredients"],
                    "nutrition": bf["nutrition"],
                    "instructions": bf.get("instructions", [])
                },
                "lunch": {
                    "recipe_id": lu["id"],
                    "recipe_name": lu["name"],
                    "reason": "Heuristic selection",
                    "servings": user.household_size,
                    "ingredients": lu["ingredients"],
                    "nutrition": lu["nutrition"],
                    "instructions": lu.get("instructions", [])
                },
                "dinner": {
                    "recipe_id": dinner["id"],
                    "recipe_name": dinner["name"],
                    "reason": "Heuristic selection",
                    "servings": user.household_size,
                    "ingredients": dinner["ingredients"],
                    "nutrition": dinner["nutrition"],
                    "instructions": dinner.get("instructions", [])
                }
            })

        summary = f"Generated a heuristic plan for {user.household_size} people."
        if is_vegetarian: summary += " Vegetarian options selected."

        plan = {
            "meal_plan": days,
            "shopping_summary": {
                "key_deals_used": [],
                "estimated_savings": 0,
                "nutritional_balance": "Standard",
                "household_size": user.household_size
            },
            "weekly_overview": summary
        }

        return plan
