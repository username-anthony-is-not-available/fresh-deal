
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.all_models import Recipe
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

    @staticmethod
    def filter_recipes(recipes: List[Dict[str, Any]], dietary_preferences: List[str], allergies: List[str]) -> List[Dict[str, Any]]:
        """
        Filters recipes based on dietary preferences (must have all) and allergies (must not have any).
        """
        if not dietary_preferences and not allergies:
            return recipes

        filtered = []
        # Normalize for case-insensitive matching
        dietary_prefs_norm = [p.lower().replace("_", "-").replace(" ", "-") for p in dietary_preferences]
        allergies_norm = [a.lower().replace("_", "-").replace(" ", "-") for a in allergies]

        for r in recipes:
            # Check dietary preferences
            if dietary_prefs_norm:
                recipe_tags_norm = [t.lower().replace("_", "-").replace(" ", "-") for t in r.get("dietary_tags", [])]
                if not all(pref in recipe_tags_norm for pref in dietary_prefs_norm):
                    continue

            # Check allergies
            if allergies_norm:
                recipe_allergens_norm = [a.lower().replace("_", "-").replace(" ", "-") for a in r.get("allergens", [])]
                if any(allergy in recipe_allergens_norm for allergy in allergies_norm):
                    continue

            filtered.append(r)
        return filtered

    @staticmethod
    def scale_ingredients(ingredients: List[Dict[str, Any]], base_servings: int, target_servings: int) -> List[Dict[str, Any]]:
        """
        Scales ingredient quantities based on target servings.
        """
        if not base_servings or not target_servings or base_servings == target_servings:
            return ingredients

        ratio = target_servings / base_servings
        scaled = []
        for ing in ingredients:
            new_ing = dict(ing)
            if "quantity" in new_ing and isinstance(new_ing["quantity"], (int, float)):
                new_ing["quantity"] = round(new_ing["quantity"] * ratio, 2)
            scaled.append(new_ing)
        return scaled
