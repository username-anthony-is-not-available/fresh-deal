
from typing import List, Dict
from sqlmodel import Session, select, func, col, or_
from app.models.all_models import Recipe, RecipeIngredient
from app.services.ingredient_matching_service import ingredient_matching_service

class RecipeMatcher:
    def __init__(self, session: Session):
        self.session = session
        self.ingredient_matcher = ingredient_matching_service

    def find_recipes_by_deals(self, deals: List[Dict], limit: int = 50) -> List[Recipe]:
        """
        Finds recipes that best match the current list of deals.
        Matching is done by counting how many ingredients in a recipe match the deal product names.

        Args:
            deals: List of deal dictionaries (must contain 'product' or 'name' key).
            limit: Max number of recipes to return.

        Returns:
            List of Recipe objects, ordered by match count descending.
        """
        # Extract deal terms (normalized)
        deal_terms = set()
        for d in deals:
            # Handle both dictionary and Deal object (if passed)
            name = d.get("product", "") if isinstance(d, dict) else d.product.name
            if name:
                # Basic tokenization: split by space, lower case
                # e.g. "Chicken Breast" -> "chicken", "breast"
                for term in name.lower().split():
                    if len(term) > 2: # Ignore small words
                        deal_terms.add(term)

        if not deal_terms:
            # If no deals, just return random recipes or top rated
            # For now, return first 50
            statement = select(Recipe).limit(limit)
            return self.session.exec(statement).all()

        # SQL Logic:
        # Use robust matching with a broad initial filter
        normalized_terms = [self.ingredient_matcher.normalize(t) for t in deal_terms if len(t) > 2]
        if not normalized_terms:
            return self.session.exec(select(Recipe).limit(limit)).all()

        # Build OR clause for partial matches
        filters = [col(RecipeIngredient.name).ilike(f"%{t}%") for t in normalized_terms]

        # We also want to match if the ingredient name is a substring of the deal term
        # But that's harder in SQL for many terms.
        # Let's stick to 'ingredient name contains deal term' as primary filter.

        statement = (
            select(RecipeIngredient.recipe_id, func.count(RecipeIngredient.id).label("score"))
            .where(or_(*filters))
            .group_by(RecipeIngredient.recipe_id)
            .order_by(func.count(RecipeIngredient.id).desc())
            .limit(limit * 2) # Get more to refine in Python if needed
        )

        results = self.session.exec(statement).all()

        if not results:
             # Fallback
             return self.session.exec(select(Recipe).limit(limit)).all()

        # Fetch full recipes
        recipe_ids = [r.recipe_id for r in results]

        # Preserve order
        recipes = []
        # Bulk fetch
        fetched = self.session.exec(select(Recipe).where(Recipe.id.in_(recipe_ids))).all()
        fetched_map = {r.id: r for r in fetched}

        for rid in recipe_ids:
            if rid in fetched_map:
                recipes.append(fetched_map[rid])

        return recipes
