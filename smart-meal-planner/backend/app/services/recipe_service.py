
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.all_models import Recipe, RecipeIngredient, RecipeRating
from sqlalchemy.orm import selectinload
from typing import List, Dict, Any
import json

class RecipeService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_recipes_as_dicts(self) -> List[Dict[str, Any]]:
        """
        Fetches all recipes from the database and returns them as a list of dicts.
        """
        statement = select(Recipe).options(
            selectinload(Recipe.ingredients),
            selectinload(Recipe.ratings)
        )
        result = await self.session.execute(statement)
        recipes = result.scalars().unique().all()

        recipe_list = []
        for recipe in recipes:
            recipe_dict = recipe.dict()
            recipe_dict['ingredients'] = [ing.name for ing in recipe.ingredients]

            # Safely parse JSON fields
            try:
                recipe_dict['dietary_tags'] = json.loads(recipe.dietary_tags_json) if recipe.dietary_tags_json else []
            except (json.JSONDecodeError, TypeError):
                recipe_dict['dietary_tags'] = []

            # Calculate average rating
            if recipe.ratings:
                avg_rating = sum(r.rating for r in recipe.ratings) / len(recipe.ratings)
                recipe_dict['average_rating'] = round(avg_rating, 2)
            else:
                recipe_dict['average_rating'] = 0

            recipe_list.append(recipe_dict)

        return recipe_list
