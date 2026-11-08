
import asyncio
import logging
from typing import Dict, List, Any
from app.services.fatsecret_service import FatSecretService
from app.services.edamam_service import EdamamService
from app.core.config import settings

logger = logging.getLogger(__name__)

class NutritionAgent:
    def __init__(self, session=None):
        self.session = session
        self.use_fatsecret = settings.FATSECRET_API_KEY and settings.FATSECRET_API_SECRET
        self.use_edamam = settings.EDAMAM_APP_ID and settings.EDAMAM_APP_KEY

        if self.use_edamam:
            self.edamam_service = EdamamService(
                app_id=settings.EDAMAM_APP_ID,
                app_key=settings.EDAMAM_APP_KEY,
            )
        elif self.use_fatsecret:
            self.fatsecret_service = FatSecretService(
                api_key=settings.FATSECRET_API_KEY,
                api_secret=settings.FATSECRET_API_SECRET,
            )

        self.use_api = self.use_edamam or self.use_fatsecret

        # Fallback to rough macro estimates
        self.ingredient_db = {
            "chicken": {"calories": 165, "protein": 31, "carbs": 0, "fats": 3.6},
            "beef": {"calories": 250, "protein": 26, "carbs": 0, "fats": 15},
            "pork": {"calories": 242, "protein": 27, "carbs": 0, "fats": 14},
            "salmon": {"calories": 208, "protein": 20, "carbs": 0, "fats": 13},
            "rice": {"calories": 130, "protein": 2.7, "carbs": 28, "fats": 0.3},
            "pasta": {"calories": 131, "protein": 5, "carbs": 25, "fats": 1.1},
            "bread": {"calories": 265, "protein": 9, "carbs": 49, "fats": 3.2},
            "oats": {"calories": 389, "protein": 16.9, "carbs": 66, "fats": 6.9},
            "egg": {"calories": 155, "protein": 13, "carbs": 1.1, "fats": 11},
            "cheese": {"calories": 402, "protein": 25, "carbs": 1.3, "fats": 33},
            "vegetable": {"calories": 30, "protein": 2, "carbs": 5, "fats": 0.2},
            "fruit": {"calories": 50, "protein": 0.5, "carbs": 12, "fats": 0.2},
            "milk": {"calories": 42, "protein": 3.4, "carbs": 5, "fats": 1},
            "oil": {"calories": 884, "protein": 0, "carbs": 0, "fats": 100},
        }

    async def estimate_meal_nutrition(self, meal_name: str, ingredients: List[Any]) -> Dict[str, Any]:
        # Convert ingredients to strings if they are dicts
        ing_strings = []
        for ing in ingredients:
            if isinstance(ing, dict):
                qty = ing.get("quantity", "")
                unit = ing.get("unit", "")
                item = ing.get("item", "")
                ing_strings.append(f"{qty} {unit} {item}".strip())
            else:
                ing_strings.append(str(ing))

        if self.use_edamam:
            nutrition = await self.edamam_service.get_nutrition_data(meal_name, ing_strings)
            if nutrition:
                return nutrition

        if self.use_fatsecret:
            # Re-using the existing placeholder logic for FatSecret if Edamam fails or is not configured
            try:
                total_nutrition = {
                    "calories": 0, "protein": 0, "carbs": 0, "fat": 0,
                    "fiber": 0
                }

                tasks = [self.fatsecret_service.search_food(ing) for ing in ing_strings]
                search_results = await asyncio.gather(*tasks, return_exceptions=True)

                food_ids_to_fetch = []
                for result in search_results:
                    if isinstance(result, Exception) or not result or not result.get('foods'):
                        continue
                    # Assume the first result is the best match
                    food_id = result['foods']['food'][0]['food_id']
                    food_ids_to_fetch.append(int(food_id))

                if food_ids_to_fetch:
                    detail_tasks = [self.fatsecret_service.get_food_details(fid) for fid in food_ids_to_fetch]
                    detail_results = await asyncio.gather(*detail_tasks, return_exceptions=True)

                    for result in detail_results:
                        if isinstance(result, Exception) or not result or 'food' not in result:
                            continue

                        servings = result['food']['servings']['serving']
                        if isinstance(servings, list):
                            serving_data = next((s for s in servings if s.get('metric_serving_unit') == 'g' and float(s.get('metric_serving_amount', 0)) == 100), servings[0])
                        else:
                            serving_data = servings

                        total_nutrition["calories"] += float(serving_data.get('calories', 0))
                        total_nutrition["protein"] += float(serving_data.get('protein', 0))
                        total_nutrition["carbs"] += float(serving_data.get('carbohydrate', 0))
                        total_nutrition["fat"] += float(serving_data.get('fat', 0))
                        total_nutrition["fiber"] += float(serving_data.get('fiber', 0))

                    return {k: int(v) for k, v in total_nutrition.items()}
            except Exception as e:
                logger.error(f"FatSecret estimation failed: {e}")

        return self._fallback_estimate_meal_nutrition(meal_name, ing_strings)

    def _fallback_estimate_meal_nutrition(self, meal_name: str, ingredients: List[str]) -> Dict[str, int]:
        total_nutrition = {"calories": 0, "protein": 0, "carbs": 0, "fats": 0}
        detected_ingredients = 0
        for ing in ingredients:
            ing_lower = ing.lower()
            match = None
            if "chicken" in ing_lower:
                match = "chicken"
            elif "beef" in ing_lower or "steak" in ing_lower:
                match = "beef"
            elif "pork" in ing_lower or "bacon" in ing_lower:
                match = "pork"
            elif "salmon" in ing_lower:
                match = "salmon"
            elif "rice" in ing_lower:
                match = "rice"
            elif "pasta" in ing_lower:
                match = "pasta"
            elif "bread" in ing_lower:
                match = "bread"
            elif "oat" in ing_lower:
                match = "oats"
            elif "egg" in ing_lower:
                match = "egg"
            elif "cheese" in ing_lower:
                match = "cheese"
            elif "milk" in ing_lower:
                match = "milk"
            elif "oil" in ing_lower or "butter" in ing_lower:
                match = "oil"
            elif any(x in ing_lower for x in ["apple", "banana", "fruit"]):
                match = "fruit"
            else:
                match = "vegetable"

            if match:
                data = self.ingredient_db[match]
                total_nutrition["calories"] += data["calories"]
                total_nutrition["protein"] += data["protein"]
                total_nutrition["carbs"] += data["carbs"]
                total_nutrition["fats"] += data["fats"]
                detected_ingredients += 1

        if detected_ingredients < 2:
            total_nutrition["calories"] += 500
        return {k: int(v) for k, v in total_nutrition.items()}

    async def validate_plan(self, plan_json: Dict[str, Any]) -> Dict[str, Any]:
        from app.models.all_models import Recipe
        import json

        total_weekly_cals = 0
        total_weekly_protein = 0
        total_weekly_carbs = 0
        total_weekly_fat = 0

        # Prefer meal_plan; otherwise accept top-level days.
        meal_plan = plan_json.get("meal_plan")
        days = (
            meal_plan
            if (
                isinstance(meal_plan, list)
                and meal_plan
                and all(isinstance(day, dict) for day in meal_plan)
            )
            else plan_json.get("days", [])
        )
        if (
            not isinstance(days, list)
            or not days
            or any(not isinstance(day, dict) for day in days)
        ):
            return plan_json

        all_meals_to_process = []

        for day in days:
            # Handle list of meals or fixed breakfast/lunch/dinner
            if "meals" in day:
                for meal in day["meals"]:
                    all_meals_to_process.append(meal)
            else:
                for meal_type in ["breakfast", "lunch", "dinner"]:
                    if day.get(meal_type):
                        all_meals_to_process.append(day[meal_type])

        # Optimize: Only estimate if nutrition is missing or empty
        nutrition_tasks = []
        meals_needing_nutrition = []
        for m in all_meals_to_process:
            if not m.get("nutrition") or not m["nutrition"].get("calories"):
                name = m.get("recipe_name") or m.get("name", "Unknown Meal")
                ingredients = m.get("ingredients", [])
                nutrition_tasks.append(self.estimate_meal_nutrition(name, ingredients))
                meals_needing_nutrition.append(m)

        if nutrition_tasks:
            nutrition_results = await asyncio.gather(*nutrition_tasks)
            for i, nutrition in enumerate(nutrition_results):
                meal = meals_needing_nutrition[i]
                meal["nutrition"] = nutrition

                # Update recipe in DB if session is available
                if self.session and meal.get("recipe_id"):
                    try:
                        recipe = self.session.get(Recipe, meal["recipe_id"])
                        if recipe:
                            recipe.nutrition_json = json.dumps(nutrition)
                            self.session.add(recipe)
                            # We don't commit here, let the caller handle it
                    except Exception as e:
                        logger.error(f"Failed to update recipe {meal['recipe_id']} nutrition: {e}")

        # Calculate summaries
        for day in days:
            day_cals = 0
            day_protein = 0
            day_carbs = 0
            day_fat = 0

            day_meals = []
            if "meals" in day:
                day_meals = day["meals"]
            else:
                day_meals = [day.get(m) for m in ["breakfast", "lunch", "dinner"] if day.get(m)]

            for meal in day_meals:
                nutrition = meal.get("nutrition", {})
                # Support both 'fat' and 'fats'
                fats = nutrition.get("fat") if nutrition.get("fat") is not None else nutrition.get("fats", 0)

                day_cals += nutrition.get("calories", 0)
                day_protein += nutrition.get("protein", 0)
                day_carbs += nutrition.get("carbs", 0)
                day_fat += fats

                total_weekly_protein += nutrition.get("protein", 0)
                total_weekly_carbs += nutrition.get("carbs", 0)
                total_weekly_fat += fats

            day["daily_summary"] = {
                "calories": int(day_cals),
                "protein": int(day_protein),
                "carbs": int(day_carbs),
                "fat": int(day_fat)
            }
            total_weekly_cals += day_cals

        num_days = len(days)
        plan_json["nutritional_summary"] = {
            "avg_daily_calories": int(total_weekly_cals / num_days) if num_days else 0,
            "avg_daily_protein": int(total_weekly_protein / num_days) if num_days else 0,
            "total_weekly_calories": int(total_weekly_cals),
            "total_weekly_protein": int(total_weekly_protein),
            "total_weekly_carbs": int(total_weekly_carbs),
            "total_weekly_fat": int(total_weekly_fat),
            "note": "Nutritional information is an estimate."
        }

        return plan_json

    async def persist_daily_nutrition_from_plan(self, user_id: int, plan_json: Dict[str, Any]):
        """
        Populates the DailyNutrition table with the data from the generated meal plan.
        """
        from app.models.all_models import DailyNutrition
        from sqlmodel import select
        from datetime import datetime, timezone

        meal_plan = plan_json.get("meal_plan") or plan_json.get("days")
        if not meal_plan or not isinstance(meal_plan, list):
            return

        if not self.session:
            logger.error("No database session provided to NutritionAgent. Persistence skipped.")
            return

        for day in meal_plan:
            day_date_str = day.get("date")
            if not day_date_str:
                continue

            try:
                day_date = datetime.strptime(day_date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            summary = day.get("daily_summary", {})

            # Check for existing record for this user and date
            statement = select(DailyNutrition).where(
                DailyNutrition.user_id == user_id,
                DailyNutrition.date == day_date
            )

            # Using exec because self.session is likely a sync Session in generate_meal_plan_task
            try:
                existing = self.session.exec(statement).first()

                if existing:
                    existing.calories = summary.get("calories", 0)
                    existing.protein = summary.get("protein", 0)
                    existing.carbs = summary.get("carbs", 0)
                    existing.fats = summary.get("fat", 0)
                    existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    self.session.add(existing)
                else:
                    new_daily = DailyNutrition(
                        user_id=user_id,
                        date=day_date,
                        calories=summary.get("calories", 0),
                        protein=summary.get("protein", 0),
                        carbs=summary.get("carbs", 0),
                        fats=summary.get("fat", 0),
                    )
                    self.session.add(new_daily)
            except Exception as e:
                logger.error(f"Failed to persist DailyNutrition for date {day_date}: {e}")

        # Note: We rely on the caller to commit the session.
