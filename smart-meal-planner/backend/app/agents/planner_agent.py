
import json
import os
import random
import logging
from typing import List, Dict, Any
from sqlmodel import Session, select
from sqlalchemy import func
from app.models.all_models import Product, Deal, Store, User, Recipe, RecipeRating, UserFavorite
from app.core.config import settings
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

class MealPlannerAgent:
    def __init__(self, session: Session):
        self.session = session
        self.llm_service = LLMService()
        self.recipes = self._load_recipes_from_db()

    def _load_recipes_from_db(self) -> List[Dict]:
        """Loads all recipes from the database and calculates their average rating."""
        avg_rating_subquery = (
            select(
                RecipeRating.recipe_id,
                func.avg(RecipeRating.rating).label("average_rating"),
            )
            .group_by(RecipeRating.recipe_id)
            .subquery()
        )

        statement = (
            select(Recipe, avg_rating_subquery.c.average_rating)
            .outerjoin(
                avg_rating_subquery, Recipe.id == avg_rating_subquery.c.recipe_id
            )
        )

        results = self.session.exec(statement).all()

        recipes_data = []
        for recipe, avg_rating in results:
            try:
                ingredients = json.loads(recipe.ingredients_json)
                instructions = json.loads(recipe.instructions_json)
                dietary_tags = json.loads(recipe.dietary_tags_json)
                allergens = json.loads(recipe.allergens_json)
                nutrition = json.loads(recipe.nutrition_json)
            except json.JSONDecodeError:
                ingredients = []
                instructions = []
                dietary_tags = []
                allergens = []
                nutrition = {}

            recipe_dict = {
                "id": recipe.id,
                "name": recipe.name,
                "cuisine": recipe.cuisine,
                "category": recipe.category,
                "meal_type": recipe.meal_type,
                "prep_time_minutes": recipe.prep_time_minutes,
                "difficulty": recipe.difficulty,
                "image_url": recipe.image_url,
                "average_rating": float(avg_rating) if avg_rating is not None else None,
                "ingredients": ingredients,
                "instructions": instructions,
                "dietary_tags": dietary_tags,
                "allergens": allergens,
                "nutrition": nutrition,
            }
            recipes_data.append(recipe_dict)
        return recipes_data

    def get_available_deals(self) -> List[Dict]:
        """Fetches active deals."""
        statement = select(Deal, Product, Store).join(Product).join(Store)
        results = self.session.exec(statement).all()

        deals_data = []
        for deal, product, store in results:
            if deal.discount_pct and deal.discount_pct > 0:
                deals_data.append({
                    "product": product.name,
                    "store": store.name,
                    "price": deal.price,
                    "discount": deal.discount_pct,
                    "category": product.category,
                    "unit": product.unit_type
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

        # Fetch user favorites
        fav_statement = select(UserFavorite.recipe_id).where(UserFavorite.user_id == user.id)
        favorite_recipe_ids = self.session.exec(fav_statement).all()

        # Filter recipes based on dietary preferences
        filtered_recipes = self.recipes
        if user.dietary_preferences:
            filtered_recipes = [
                r
                for r in self.recipes
                if all(
                    pref in r.get("dietary_tags", [])
                    for pref in user.dietary_preferences
                )
            ]

        # Sort by rating, putting highly-rated recipes first
        filtered_recipes.sort(key=lambda r: r.get("average_rating") or 2.5, reverse=True)

        try:
            plan = self.llm_service.generate_meal_plan(user_prefs, deals, filtered_recipes, favorite_recipe_ids)
            validated_plan = self._validate_and_enrich(plan)
            return validated_plan
        except Exception as e:
            logger.error(f"LLM generation failed or validation failed: {e}. Falling back to heuristic plan.")
            return self._generate_structured_plan(user)

    def _validate_and_enrich(self, plan: Dict) -> Dict:
        """Validates LLM output and adds missing data."""
        recipe_map = {r["id"]: r for r in self.recipes}

        if "meal_plan" not in plan:
            raise ValueError("Invalid plan structure from LLM")

        for day in plan["meal_plan"]:
            for meal_type in ["breakfast", "lunch", "dinner"]:
                meal_info = day.get(meal_type)
                if not meal_info:
                    continue

                recipe_id = meal_info.get("recipe_id")
                recipe_details = recipe_map.get(recipe_id)

                if not recipe_details:
                    # Fallback if ID is invalid
                    candidates = [r for r in self.recipes if r.get("meal_type", "").lower() == meal_type.lower()]
                    if candidates:
                        recipe_details = random.choice(candidates)
                        meal_info["recipe_id"] = recipe_details["id"]
                        meal_info["recipe_name"] = recipe_details.get("name")
                        meal_info["reason"] = meal_info.get("reason", "") + " (Fallback selection)"

                if recipe_details:
                    # Enrich with data from our DB-loaded recipe list
                    meal_info["ingredients"] = recipe_details.get("ingredients", [])
                    meal_info["nutrition"] = recipe_details.get("nutrition", {})
                    meal_info["instructions"] = recipe_details.get("instructions", [])
                    meal_info["tags"] = recipe_details.get("tags", [])
                    meal_info["image"] = recipe_details.get("image_url", "/placeholder.jpg")
        return plan

    def _generate_structured_plan(self, user: User) -> Dict[str, Any]:
        """Fallback heuristic plan generation."""
        week_dates = self.llm_service.get_next_week_dates()

        # Simple filtering for fallback
        suitable_recipes = self.recipes

        breakfasts = [r for r in suitable_recipes if r.get("meal_type") == "Breakfast"]
        lunches = [r for r in suitable_recipes if r.get("meal_type") == "Lunch"]
        dinners = [r for r in suitable_recipes if r.get("meal_type") == "Dinner"]

        if not breakfasts: breakfasts = suitable_recipes
        if not lunches: lunches = suitable_recipes
        if not dinners: dinners = suitable_recipes

        days = []
        used_dinner_ids = set()

        for i in range(7):
            date_info = week_dates[i]
            dinner = next((d for d in dinners if d["id"] not in used_dinner_ids), random.choice(dinners))
            used_dinner_ids.add(dinner["id"])

            bf = random.choice(breakfasts)
            lu = random.choice(lunches)

            days.append({
                "day": i + 1, "day_name": date_info["day_name"], "date": date_info["date"],
                "breakfast": self._format_meal(bf, user.household_size),
                "lunch": self._format_meal(lu, user.household_size),
                "dinner": self._format_meal(dinner, user.household_size)
            })

        return {
            "meal_plan": days,
            "shopping_summary": { "household_size": user.household_size, "weekly_overview": "Heuristic fallback plan." }
        }

    def _format_meal(self, recipe: Dict, household_size: int) -> Dict:
        return {
            "recipe_id": recipe["id"],
            "recipe_name": recipe["name"],
            "reason": "Heuristic selection",
            "servings": household_size,
            "ingredients": recipe.get("ingredients", []),
            "nutrition": recipe.get("nutrition", {}),
            "instructions": recipe.get("instructions", [])
        }
