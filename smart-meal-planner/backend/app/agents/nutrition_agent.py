
import asyncio
import logging
import os
import re
import json
import sqlite3
from typing import Dict, List, Any
from app.services.fatsecret_service import FatSecretService
from app.services.edamam_service import EdamamService
from app.services.nutrition_helpers import (
    extract_day_meals,
    extract_plan_days,
    normalize_nutrition,
    parse_nutrition_json,
)
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

        # Canadian Nutrient File (CNF) / USDA Foundation Foods offline database
        self.offline_nutrition_db = {}
        data_file = os.path.join(os.path.dirname(__file__), "..", "data", "offline_nutrition.json")
        try:
            if os.path.exists(data_file):
                with open(data_file, "r", encoding="utf-8") as f:
                    self.offline_nutrition_db = json.load(f)
                logger.info(f"Loaded {len(self.offline_nutrition_db)} CNF/USDA offline nutrition profiles.")
        except Exception as e:
            logger.warning(f"Failed to load offline nutrition database: {e}")

        # Local SQLite cache for nutrition resolution
        self.cache_dir = os.path.join(os.getcwd(), ".cache")
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            self.cache_db = os.path.join(self.cache_dir, "nutrition_cache.sqlite")
            with sqlite3.connect(self.cache_db) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS ingredient_nutrition (
                        query TEXT PRIMARY KEY,
                        calories REAL,
                        protein REAL,
                        carbs REAL,
                        fats REAL,
                        fiber REAL
                    )
                ''')
                conn.commit()
        except Exception as e:
            self.cache_db = None

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

    def resolve_offline_nutrition(self, ingredients: List[str]) -> Dict[str, Any]:
        """Resolves nutritional profile locally using Canadian Nutrient File / USDA data."""
        total = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fats": 0.0, "fiber": 0.0, "detected_count": 0}

        for ing in ingredients:
            ing_lower = ing.lower().strip()
            if not ing_lower:
                continue

            # Check SQLite persistent cache first
            if getattr(self, "cache_db", None):
                try:
                    with sqlite3.connect(self.cache_db) as conn:
                        cur = conn.cursor()
                        cur.execute("SELECT calories, protein, carbs, fats, fiber FROM ingredient_nutrition WHERE query = ?", (ing_lower,))
                        row = cur.fetchone()
                        if row:
                            total["calories"] += row[0]
                            total["protein"] += row[1]
                            total["carbs"] += row[2]
                            total["fats"] += row[3]
                            total["fiber"] += row[4]
                            total["detected_count"] += 1
                            continue
                except Exception:
                    pass

            # Parse quantity (supports decimals, fractions, and mixed fractions like "1 1/2") and unit
            qty_match = re.search(
                r"^(\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)\s*([a-zA-ZÀ-ÿ\.%]+)?",
                ing_lower,
            )
            qty = 1.0
            unit = ""
            if qty_match:
                qty_str = qty_match.group(1).strip()
                unit = (qty_match.group(2) or "").lower().rstrip(".")
                try:
                    if " " in qty_str and "/" in qty_str:
                        whole_str, frac_str = qty_str.split(None, 1)
                        num, den = frac_str.split("/", 1)
                        qty = float(whole_str) + (float(num) / float(den))
                    elif "/" in qty_str:
                        num, den = qty_str.split("/", 1)
                        qty = float(num) / float(den)
                    else:
                        qty = float(qty_str)
                except (ValueError, ZeroDivisionError):
                    qty = 1.0

            # Estimate weight in grams based on unit (CNF baseline is per 100g)
            if unit in ["g", "gram", "grams"]:
                grams = qty
            elif unit in ["kg", "kilogram", "kilograms"]:
                grams = qty * 1000.0
            elif unit in ["lb", "lbs", "pound", "pounds"]:
                grams = qty * 453.59
            elif unit in ["oz", "ounce", "ounces"]:
                grams = qty * 28.35
            elif unit in ["ml", "milliliter", "milliliters"]:
                grams = qty
            elif unit in ["l", "liter", "liters", "litre", "litres"]:
                grams = qty * 1000.0
            elif unit in ["tbsp", "tablespoon", "tablespoons", "cas"] or "c. à soupe" in ing_lower:
                grams = qty * 15.0
            elif unit in ["tsp", "teaspoon", "teaspoons", "cat"] or "c. à thé" in ing_lower:
                grams = qty * 5.0
            elif unit in ["cup", "tasse", "tasses", "cups"]:
                grams = qty * 150.0
            elif unit in ["each", "un", "unit", "piece", "pieces", "egg", "oeuf"] or not unit:
                grams = qty * 80.0
            elif unit in ["can", "cans", "conserve"]:
                grams = qty * 400.0
            elif unit in ["clove", "cloves", "gousse", "gousses"]:
                grams = qty * 5.0
            else:
                # Unit token was part of the ingredient name (e.g. "2 chicken breasts"); still scale by quantity.
                grams = qty * 100.0

            multiplier = max(grams / 100.0, 0.1)

            # Match against CNF/USDA offline database, preferring longest alias match
            match = None
            best_alias_len = 0
            if self.offline_nutrition_db:
                for key, data in self.offline_nutrition_db.items():
                    aliases = data.get("aliases", []) + [key]
                    for alias in aliases:
                        alias_lower = alias.lower()
                        if alias_lower in ing_lower and len(alias_lower) > best_alias_len:
                            match = data
                            best_alias_len = len(alias_lower)

            if match:
                cals = match["calories"] * multiplier
                prot = match["protein"] * multiplier
                carbs = match["carbs"] * multiplier
                fats = match["fats"] * multiplier
                fib = match.get("fiber", 0.0) * multiplier

                total["calories"] += cals
                total["protein"] += prot
                total["carbs"] += carbs
                total["fats"] += fats
                total["fiber"] += fib
                total["detected_count"] += 1

                # Cache in SQLite
                if getattr(self, "cache_db", None):
                    try:
                        with sqlite3.connect(self.cache_db) as conn:
                            conn.execute(
                                "INSERT OR REPLACE INTO ingredient_nutrition VALUES (?, ?, ?, ?, ?, ?)",
                                (ing_lower, cals, prot, carbs, fats, fib)
                            )
                            conn.commit()
                    except Exception:
                        pass

        return {
            "calories": round(total["calories"]),
            "protein": round(total["protein"]),
            "carbs": round(total["carbs"]),
            "fats": round(total["fats"]),
            "fat": round(total["fats"]),
            "fiber": round(total["fiber"]),
            "detected_count": total["detected_count"],
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

        # 1. Resolve through local offline CNF/USDA database first
        local_nutrition = self.resolve_offline_nutrition(ing_strings)
        detected = local_nutrition.get("detected_count", 0)

        # If all ingredients or at least 80% resolved locally, or if no external APIs are configured, return local result
        if (not self.use_api) or (detected > 0 and detected >= len(ing_strings)):
            if local_nutrition.get("calories", 0) > 0:
                return {
                    "calories": int(local_nutrition["calories"]),
                    "protein": int(local_nutrition["protein"]),
                    "carbs": int(local_nutrition["carbs"]),
                    "fat": int(local_nutrition["fat"]),
                    "fats": int(local_nutrition["fats"]),
                    "fiber": int(local_nutrition["fiber"]),
                }

        # 2. Query external APIs on cache misses if configured
        if self.use_edamam:
            nutrition = await self.edamam_service.get_nutrition_data(meal_name, ing_strings)
            if nutrition:
                return nutrition

        if self.use_fatsecret:
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

        # 3. Fallback to offline local nutrition or heuristic estimate
        if local_nutrition.get("calories", 0) > 0:
            return {
                "calories": int(local_nutrition["calories"]),
                "protein": int(local_nutrition["protein"]),
                "carbs": int(local_nutrition["carbs"]),
                "fat": int(local_nutrition["fat"]),
                "fats": int(local_nutrition["fats"]),
                "fiber": int(local_nutrition["fiber"]),
            }

        return self._fallback_estimate_meal_nutrition(meal_name, ing_strings)

    def _fallback_estimate_meal_nutrition(self, meal_name: str, ingredients: List[str]) -> Dict[str, int]:
        total_nutrition = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fats": 0.0, "fiber": 0.0}
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
        rounded = {k: int(round(v)) for k, v in total_nutrition.items()}
        rounded["fat"] = rounded["fats"]
        return rounded

    async def _fetch_recipe(self, recipe_id: int):
        """Fetch a Recipe from either a synchronous Session or AsyncSession."""
        from app.models.all_models import Recipe
        from sqlalchemy.ext.asyncio import AsyncSession

        if not self.session:
            return None
        if isinstance(self.session, AsyncSession):
            return await self.session.get(Recipe, recipe_id)
        return self.session.get(Recipe, recipe_id)

    async def validate_plan(self, plan_json: Dict[str, Any]) -> Dict[str, Any]:
        days = extract_plan_days(plan_json)
        if not days:
            return plan_json

        total_weekly_cals = 0.0
        total_weekly_protein = 0.0
        total_weekly_carbs = 0.0
        total_weekly_fat = 0.0

        all_meals_to_process = [
            meal for day in days for meal in extract_day_meals(day)
        ]

        # Populate missing or incomplete nutrition: check stored Recipe.nutrition_json first, then estimate.
        nutrition_tasks = []
        meals_needing_nutrition = []
        for m in all_meals_to_process:
            existing_nut = m.get("nutrition")
            has_calories = isinstance(existing_nut, dict) and (existing_nut.get("calories") or 0) > 0
            if not has_calories:
                recipe_id = m.get("recipe_id")
                if self.session and isinstance(recipe_id, int):
                    try:
                        recipe = await self._fetch_recipe(recipe_id)
                        if recipe and recipe.nutrition_json:
                            parsed = parse_nutrition_json(recipe.nutrition_json)
                            if (parsed.get("calories") or 0) > 0:
                                m["nutrition"] = parsed
                                continue
                    except Exception as e:
                        logger.error(f"Failed to load recipe {recipe_id} nutrition: {e}")

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
                if self.session and isinstance(meal.get("recipe_id"), int):
                    try:
                        recipe = await self._fetch_recipe(meal["recipe_id"])
                        if recipe:
                            recipe.nutrition_json = json.dumps(nutrition)
                            self.session.add(recipe)
                    except Exception as e:
                        logger.error(f"Failed to update recipe {meal['recipe_id']} nutrition: {e}")

        # Calculate summaries accurately using float accumulation before rounding.
        for day in days:
            day_cals = 0.0
            day_protein = 0.0
            day_carbs = 0.0
            day_fat = 0.0

            for meal in extract_day_meals(day):
                norm = normalize_nutrition(meal.get("nutrition"))
                day_cals += norm["calories"]
                day_protein += norm["protein"]
                day_carbs += norm["carbs"]
                day_fat += norm["fat"]

            day["daily_summary"] = {
                "calories": int(round(day_cals)),
                "protein": int(round(day_protein)),
                "carbs": int(round(day_carbs)),
                "fat": int(round(day_fat)),
            }
            total_weekly_cals += day_cals
            total_weekly_protein += day_protein
            total_weekly_carbs += day_carbs
            total_weekly_fat += day_fat

        num_days = len(days)
        plan_json["nutritional_summary"] = {
            "avg_daily_calories": int(round(total_weekly_cals / num_days)) if num_days else 0,
            "avg_daily_protein": int(round(total_weekly_protein / num_days)) if num_days else 0,
            "total_weekly_calories": int(round(total_weekly_cals)),
            "total_weekly_protein": int(round(total_weekly_protein)),
            "total_weekly_carbs": int(round(total_weekly_carbs)),
            "total_weekly_fat": int(round(total_weekly_fat)),
            "note": "Nutritional information is an estimate.",
        }

        return plan_json

    async def persist_daily_nutrition_from_plan(self, user_id: int, plan_json: Dict[str, Any]):
        """
        Populates the DailyNutrition table with the data from the generated meal plan.
        Supports both synchronous Session and AsyncSession.
        """
        from app.models.all_models import DailyNutrition
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlmodel import select
        from datetime import datetime, timezone

        meal_plan = extract_plan_days(plan_json)
        if not meal_plan:
            return

        if not self.session:
            logger.error("No database session provided to NutritionAgent. Persistence skipped.")
            return

        is_async = isinstance(self.session, AsyncSession)

        for day in meal_plan:
            day_date_str = day.get("date")
            if not day_date_str:
                continue

            try:
                day_date = datetime.strptime(day_date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            day_meals = extract_day_meals(day)
            meal_fiber = sum(normalize_nutrition(m.get("nutrition"))["fiber"] for m in day_meals)

            summary = day.get("daily_summary")
            if isinstance(summary, dict) and summary:
                norm_summary = normalize_nutrition(summary)
                if norm_summary["fiber"] == 0.0 and meal_fiber > 0.0:
                    norm_summary["fiber"] = meal_fiber
            else:
                norm_summary = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "fiber": 0.0}
                for m in day_meals:
                    norm_m = normalize_nutrition(m.get("nutrition"))
                    for key in norm_summary:
                        norm_summary[key] += norm_m[key]

            statement = select(DailyNutrition).where(
                DailyNutrition.user_id == user_id,
                DailyNutrition.date == day_date,
            )

            try:
                if is_async:
                    result = await self.session.execute(statement)
                    existing = result.scalars().first()
                elif hasattr(self.session, "exec"):
                    existing = self.session.exec(statement).first()
                else:
                    existing = self.session.execute(statement).scalars().first()

                if existing:
                    existing.calories = norm_summary["calories"]
                    existing.protein = norm_summary["protein"]
                    existing.carbs = norm_summary["carbs"]
                    existing.fats = norm_summary["fat"]
                    existing.fiber = norm_summary["fiber"]
                    existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    self.session.add(existing)
                else:
                    new_daily = DailyNutrition(
                        user_id=user_id,
                        date=day_date,
                        calories=norm_summary["calories"],
                        protein=norm_summary["protein"],
                        carbs=norm_summary["carbs"],
                        fats=norm_summary["fat"],
                        fiber=norm_summary["fiber"],
                    )
                    self.session.add(new_daily)
            except Exception as e:
                logger.error(f"Failed to persist DailyNutrition for date {day_date}: {e}")

        # Note: We rely on the caller to commit the session.
