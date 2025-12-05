
from typing import Dict, List, Any

class NutritionAgent:
    def __init__(self):
        # Rough macro estimates per 100g or serving unit for common ingredients
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
            "vegetable": {"calories": 30, "protein": 2, "carbs": 5, "fats": 0.2}, # Generic veg
            "fruit": {"calories": 50, "protein": 0.5, "carbs": 12, "fats": 0.2}, # Generic fruit
            "milk": {"calories": 42, "protein": 3.4, "carbs": 5, "fats": 1},
            "oil": {"calories": 884, "protein": 0, "carbs": 0, "fats": 100},
        }

    def estimate_meal_nutrition(self, meal_name: str, ingredients: List[str]) -> Dict[str, int]:
        """
        Estimates the nutritional content of a meal based on its ingredients.
        This is a heuristic estimation.
        """
        total_nutrition = {"calories": 0, "protein": 0, "carbs": 0, "fats": 0}

        # Heuristic: Assume a standard meal has ~400-600g of food total
        # We'll just sum up "servings" of recognized keywords

        detected_ingredients = 0

        for ing in ingredients:
            ing_lower = ing.lower()
            match = None

            if "chicken" in ing_lower: match = "chicken"
            elif "beef" in ing_lower or "steak" in ing_lower or "burger" in ing_lower: match = "beef"
            elif "pork" in ing_lower or "bacon" in ing_lower or "ham" in ing_lower: match = "pork"
            elif "fish" in ing_lower or "salmon" in ing_lower or "shrimp" in ing_lower: match = "salmon"
            elif "rice" in ing_lower: match = "rice"
            elif "pasta" in ing_lower or "spaghetti" in ing_lower or "macaroni" in ing_lower: match = "pasta"
            elif "bread" in ing_lower or "toast" in ing_lower or "sandwich" in ing_lower: match = "bread"
            elif "oat" in ing_lower: match = "oats"
            elif "egg" in ing_lower: match = "egg"
            elif "cheese" in ing_lower: match = "cheese"
            elif "milk" in ing_lower or "yogurt" in ing_lower: match = "milk"
            elif "oil" in ing_lower or "butter" in ing_lower: match = "oil"
            elif any(x in ing_lower for x in ["apple", "banana", "berry", "orange", "fruit"]): match = "fruit"
            else: match = "vegetable" # Default to veg for unknown items (low calorie safe bet)

            if match:
                data = self.ingredient_db[match]
                # Assume 1 serving = 100g for calculation simplicity
                total_nutrition["calories"] += data["calories"]
                total_nutrition["protein"] += data["protein"]
                total_nutrition["carbs"] += data["carbs"]
                total_nutrition["fats"] += data["fats"]
                detected_ingredients += 1

        # If we didn't find much, apply a baseline based on meal name keywords
        if detected_ingredients < 2:
             if "salad" in meal_name.lower():
                 total_nutrition["calories"] += 300
                 total_nutrition["carbs"] += 20
                 total_nutrition["fats"] += 20
             else:
                 total_nutrition["calories"] += 500
                 total_nutrition["protein"] += 20
                 total_nutrition["carbs"] += 50
                 total_nutrition["fats"] += 20

        return {k: int(v) for k, v in total_nutrition.items()}

    def validate_plan(self, plan_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decorates the plan with nutritional info and checks for balance.
        """
        total_weekly_cals = 0
        total_weekly_protein = 0

        for day in plan_json["days"]:
            day_cals = 0
            for meal in day["meals"]:
                nutrition = self.estimate_meal_nutrition(meal["name"], meal["ingredients"])
                meal["nutrition"] = nutrition # Inject into the JSON
                day_cals += nutrition["calories"]
                total_weekly_protein += nutrition["protein"]

            day["daily_summary"] = {
                "calories": day_cals,
                "protein": int(day_cals * 0.2 / 4), # Rough estimation logic
                "carbs": int(day_cals * 0.5 / 4),
                "fats": int(day_cals * 0.3 / 9)
            }
            total_weekly_cals += day_cals

        avg_daily_cals = total_weekly_cals / len(plan_json["days"])
        plan_json["nutritional_summary"] = {
             "avg_daily_calories": int(avg_daily_cals),
             "avg_daily_protein": int(total_weekly_protein / 7),
             "note": "Estimated based on ingredients."
        }

        return plan_json
