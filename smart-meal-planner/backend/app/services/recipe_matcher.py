from typing import List, Dict, Any, Optional
from sqlmodel import Session, select, func, col, or_
from app.models.all_models import Recipe, RecipeIngredient
from app.services.ingredient_matching_service import ingredient_matching_service
from app.services.substitution_service import substitution_service

class RecipeMatcher:
    def __init__(self, session: Session):
        self.session = session
        self.ingredient_matcher = ingredient_matching_service
        self.substitution_service = substitution_service

    def find_recipes_by_deals(self, deals: List[Dict], limit: int = 50, include_substitutions: bool = True) -> List[Recipe]:
        """
        Finds recipes that best match the current list of deals.
        Matching is done by counting how many ingredients in a recipe match
        the deal product names or active deal substitutes.

        Args:
            deals: List of deal dictionaries (must contain 'product' or 'name' key).
            limit: Max number of recipes to return.
            include_substitutions: Whether to include valid swaps from substitutions.json.

        Returns:
            List of Recipe objects, ordered by match count descending.
        """
        deal_terms = set()
        substitutions = self.substitution_service._load_substitutions()

        for d in deals:
            name = d.get("product", "") if isinstance(d, dict) else getattr(getattr(d, "product", None), "name", "")
            if name:
                for term in name.lower().split():
                    if len(term) > 2:
                        deal_terms.add(term)
                        # Add substitute terms
                        if include_substitutions:
                            for prim, subs in substitutions.items():
                                if term in prim.lower():
                                    for s in subs:
                                        for st in s.lower().split():
                                            if len(st) > 2:
                                                deal_terms.add(st)

        if not deal_terms:
            statement = select(Recipe).limit(limit)
            return self.session.exec(statement).all()

        normalized_terms = [self.ingredient_matcher.normalize(t) for t in deal_terms if len(t) > 2]
        if not normalized_terms:
            return self.session.exec(select(Recipe).limit(limit)).all()

        filters = [col(RecipeIngredient.name).ilike(f"%{t}%") for t in normalized_terms[:100]]

        statement = (
            select(RecipeIngredient.recipe_id, func.count(RecipeIngredient.id).label("score"))
            .where(or_(*filters))
            .group_by(RecipeIngredient.recipe_id)
            .order_by(func.count(RecipeIngredient.id).desc())
            .limit(limit * 2)
        )

        results = self.session.exec(statement).all()

        if not results:
             return self.session.exec(select(Recipe).limit(limit)).all()

        recipe_ids = [r.recipe_id for r in results]
        fetched = self.session.exec(select(Recipe).where(Recipe.id.in_(recipe_ids))).all()
        fetched_map = {r.id: r for r in fetched}

        recipes = []
        for rid in recipe_ids:
            if rid in fetched_map:
                recipes.append(fetched_map[rid])

        return recipes[:limit]
