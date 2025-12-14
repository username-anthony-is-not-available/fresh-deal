
import asyncio
from typing import Dict, List, Any
from app.services.fatsecret_service import FatSecretService
from app.core.config import settings

class NutritionAgent:
    def __init__(self):
        self.use_api = settings.FATSECRET_API_KEY and settings.FATSECRET_API_SECRET
        if self.use_api:
            self.fatsecret_service = FatSecretService(
                api_key=settings.FATSECRET_API_KEY,
                api_secret=settings.FATSECRET_API_SECRET,
            )
        else:
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

    async def estimate_meal_nutrition(self, meal_name: str, ingredients: List[str]) -> Dict[str, Any]:
        if not self.use_api:
            return self._fallback_estimate_meal_nutrition(meal_name, ingredients)

        total_nutrition = {
            "calories": 0, "protein": 0, "carbs": 0, "fats": 0,
            "vitamins": {}, "minerals": {}
        }

        # In a real implementation, we would parse ingredients for quantity and units
        # For now, we'll just get nutrition for the ingredient name as a proxy
        tasks = [self.fatsecret_service.search_food(ing) for ing in ingredients]
        search_results = await asyncio.gather(*tasks, return_exceptions=True)

        food_ids_to_fetch = []
        for result in search_results:
            if isinstance(result, Exception) or not result.get('foods'):
                continue
            # Assume the first result is the best match
            food_id = result['foods']['food'][0]['food_id']
            food_ids_to_fetch.append(int(food_id))

        if not food_ids_to_fetch:
            return self._fallback_estimate_meal_nutrition(meal_name, ingredients)

        detail_tasks = [self.fatsecret_service.get_food_details(fid) for fid in food_ids_to_fetch]
        detail_results = await asyncio.gather(*detail_tasks, return_exceptions=True)

        for result in detail_results:
            if isinstance(result, Exception) or 'food' not in result:
                continue

            # This part is highly dependent on the actual API response structure
            # The following is a placeholder based on expected data
            servings = result['food']['servings']['serving']
            # Find a standard 100g serving if possible, otherwise take the first
            serving_data = next((s for s in servings if s.get('metric_serving_unit') == 'g' and float(s.get('metric_serving_amount', 0)) == 100), servings[0])

            total_nutrition["calories"] += float(serving_data.get('calories', 0))
            total_nutrition["protein"] += float(serving_data.get('protein', 0))
            total_nutrition["carbs"] += float(serving_data.get('carbohydrate', 0))
            total_nutrition["fats"] += float(serving_data.get('fat', 0))
            # Mock micronutrient aggregation
            # In reality, parse this from the response and sum it up
            total_nutrition["minerals"]["iron"] = total_nutrition["minerals"].get("iron", 0) + 1 # placeholder
            total_nutrition["vitamins"]["c"] = total_nutrition["vitamins"].get("c", 0) + 5 # placeholder

        return {k: int(v) if isinstance(v, (int, float)) else v for k, v in total_nutrition.items()}

    def _fallback_estimate_meal_nutrition(self, meal_name: str, ingredients: List[str]) -> Dict[str, int]:
        total_nutrition = {"calories": 0, "protein": 0, "carbs": 0, "fats": 0}
        detected_ingredients = 0
        for ing in ingredients:
            ing_lower = ing.lower()
            match = None
            if "chicken" in ing_lower: match = "chicken"
            elif "beef" in ing_lower or "steak" in ing_lower: match = "beef"
            elif "pork" in ing_lower or "bacon" in ing_lower: match = "pork"
            elif "salmon" in ing_lower: match = "salmon"
            elif "rice" in ing_lower: match = "rice"
            elif "pasta" in ing_lower: match = "pasta"
            elif "bread" in ing_lower: match = "bread"
            elif "oat" in ing_lower: match = "oats"
            elif "egg" in ing_lower: match = "egg"
            elif "cheese" in ing_lower: match = "cheese"
            elif "milk" in ing_lower: match = "milk"
            elif "oil" in ing_lower or "butter" in ing_lower: match = "oil"
            elif any(x in ing_lower for x in ["apple", "banana", "fruit"]): match = "fruit"
            else: match = "vegetable"

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
        total_weekly_cals = 0
        total_weekly_protein = 0

        all_meals_to_process = []
        for day in plan_json["days"]:
            for meal in day["meals"]:
                all_meals_to_process.append(meal)

        nutrition_tasks = [self.estimate_meal_nutrition(m['name'], m['ingredients']) for m in all_meals_to_process]
        nutrition_results = await asyncio.gather(*nutrition_tasks)

        # Re-inject results
        result_idx = 0
        for day in plan_json["days"]:
            day_cals = 0
            for meal in day["meals"]:
                nutrition = nutrition_results[result_idx]
                meal["nutrition"] = nutrition
                day_cals += nutrition["calories"]
                total_weekly_protein += nutrition.get("protein", 0)
                result_idx += 1

            day["daily_summary"] = {"calories": day_cals}
            total_weekly_cals += day_cals

        avg_daily_cals = total_weekly_cals / len(plan_json["days"]) if plan_json["days"] else 0
        plan_json["nutritional_summary"] = {
            "avg_daily_calories": int(avg_daily_cals),
            "avg_daily_protein": int(total_weekly_protein / 7) if total_weekly_protein else 0,
            "note": "Nutritional information is an estimate."
        }

        return plan_json
