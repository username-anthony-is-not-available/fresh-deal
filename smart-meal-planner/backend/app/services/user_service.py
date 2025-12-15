import json
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.all_models import User, MealPlan, Recipe
from app.schemas import UserUpdate
from typing import Optional

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

        totals = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0}
        num_days = len(plan_data.get("meal_plan", []))

        for day in plan_data.get("meal_plan", []):
            for meal_type in ["breakfast", "lunch", "dinner"]:
                meal = day.get(meal_type, {})
                if meal:
                    recipe_id = meal.get("recipe_id")
                    if recipe_id:
                        recipe = await self.session.get(Recipe, recipe_id)
                        if recipe and recipe.nutrition_json:
                            nutrition_data = json.loads(recipe.nutrition_json)
                            for key in totals:
                                totals[key] += nutrition_data.get(key, 0)

        return {
            "totals": totals,
            "daily_averages": {key: round(value / num_days, 2) if num_days > 0 else 0 for key, value in totals.items()}
        }
