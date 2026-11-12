import json
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.all_models import User, MealPlan, Recipe
from app.schemas import UserUpdate
from app.services.nutrition_helpers import (
    NUTRIENT_KEYS,
    extract_day_meals,
    extract_plan_days,
    normalize_nutrition,
    parse_nutrition_json,
)
from typing import Dict, Optional

class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user(self, user_id: int) -> Optional[User]:
        result = await self.session.get(User, user_id)
        return result

    async def update_user(self, user_id: int, user_update: UserUpdate) -> Optional[User]:
        user = await self.get_user(user_id)
        if not user:
            return None

        update_data = user_update.model_dump(exclude_unset=True)

        if 'allergies' in update_data and update_data['allergies'] is not None:
            user.allergies = update_data.pop('allergies')

        if 'preferred_loyalty_programs' in update_data and update_data['preferred_loyalty_programs'] is not None:
            user.preferred_loyalty_programs = update_data.pop('preferred_loyalty_programs')

        for key, value in update_data.items():
            setattr(user, key, value)

        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_meal_plan_nutrition_summary(self, user_id: int) -> dict:
        user = await self.get_user(user_id)
        if not user:
            return {}

        # Get the latest meal plan
        statement = select(MealPlan).where(MealPlan.user_id == user_id).order_by(MealPlan.created_at.desc())
        result = await self.session.execute(statement)
        plan = result.scalars().first()

        if not plan:
            return {}

        plan_data = json.loads(plan.content_json)
        days = extract_plan_days(plan_data)

        totals: Dict[str, float] = {key: 0.0 for key in NUTRIENT_KEYS}
        num_days = len(days)

        # Prefetch all referenced recipes in one query to avoid N+1 database roundtrips.
        all_meals = [meal for day in days for meal in extract_day_meals(day)]
        recipe_ids = {
            meal["recipe_id"]
            for meal in all_meals
            if isinstance(meal.get("recipe_id"), int)
        }
        recipe_nutrition_by_id: Dict[int, Dict[str, float]] = {}
        if recipe_ids:
            rec_stmt = select(Recipe).where(Recipe.id.in_(recipe_ids))
            rec_result = await self.session.execute(rec_stmt)
            for recipe in rec_result.scalars().all():
                parsed = parse_nutrition_json(recipe.nutrition_json)
                if parsed:
                    recipe_nutrition_by_id[recipe.id] = normalize_nutrition(parsed)

        for meal in all_meals:
            recipe_id = meal.get("recipe_id")
            if isinstance(recipe_id, int) and recipe_id in recipe_nutrition_by_id:
                nutrition_data = recipe_nutrition_by_id[recipe_id]
            else:
                nutrition_data = normalize_nutrition(meal.get("nutrition"))

            for key in NUTRIENT_KEYS:
                totals[key] += nutrition_data.get(key, 0.0)

        rounded_totals = {key: round(value, 2) for key, value in totals.items()}
        return {
            "totals": rounded_totals,
            "daily_averages": {
                key: round(value / num_days, 2) if num_days > 0 else 0
                for key, value in totals.items()
            },
        }
