
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select, func, col
from sqlalchemy.orm import selectinload
from app.models.all_models import Recipe, RecipeIngredient, Deal

class RecipeMatcher:
    def __init__(self, session: Session):
        self.session = session

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
        # SELECT recipe_id, COUNT(*) as match_count
        # FROM recipeingredient
        # WHERE name LIKE any(deal_terms)
        # GROUP BY recipe_id
        # ORDER BY match_count DESC

        # Since SQLite/Postgres 'LIKE ANY' syntax differs, we iterate construction of OR clause
        # or use exact matching on 'name' if we trust normalization.
        # Let's try to match partials.

        # Optimized approach: Filter RecipeIngredients that contain any deal term
        # Then aggregate.

        # We construct a list of like clauses
        # But for 64k recipes, this might be slow if deal_terms is large (e.g. 50 deals * 2 terms = 100 terms).
        # Better: use 'IN' clause on exact normalized matches if possible.
        # But "chicken breast" deal vs "chicken" ingredient.
        # Let's try exact match on single words first.

        statement = (
            select(RecipeIngredient.recipe_id, func.count(RecipeIngredient.id).label("score"))
            .where(col(RecipeIngredient.name).in_(deal_terms))
            .group_by(RecipeIngredient.recipe_id)
            .order_by(func.count(RecipeIngredient.id).desc())
            .limit(limit)
        )

        # Improved: We really want LIKE matches.
        # "chicken" deal should match "chicken breast" ingredient.
        # AND "chicken breast" deal should match "chicken" ingredient.

        # Let's keep it simple:
        # Find all recipe IDs that have at least one matching ingredient.
        # We will do this in Python for flexibility if the dataset size allows (64k recipes * 10 ings = 640k rows - OK for in-memory set intersection if needed, but DB is better).

        # Hybrid Approach:
        # Fetch all RecipeIngredients. (It's lightweight: id, recipe_id, name).
        # Filter in Python.

        # For MVP/PoC:
        # Let's try a direct LIKE query construction for top terms.

        # Let's do a simple exact match on words in the DB for now.
        # If deal is "Chicken Breast", we look for ingredients named "chicken" or "breast".

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
