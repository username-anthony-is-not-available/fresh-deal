import json
import logging
from typing import Dict, List, Optional, Any
from app.services.ingredient_matching_service import ingredient_matching_service

logger = logging.getLogger(__name__)

class SubstitutionService:
    _substitutions: Optional[Dict[str, List[str]]] = None

    def __init__(self, filepath: str = "app/data/substitutions.json"):
        self.filepath = filepath
        self.matcher = ingredient_matching_service

    def _load_substitutions(self) -> Dict[str, List[str]]:
        if self._substitutions is None:
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self._substitutions = json.load(f)
            except FileNotFoundError:
                try:
                    import os
                    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    alt_path = os.path.join(base_path, "data", "substitutions.json")
                    with open(alt_path, "r", encoding="utf-8") as f:
                        self._substitutions = json.load(f)
                except Exception as e:
                    logger.error(f"Error loading substitutions: {e}")
                    self._substitutions = {}
        return self._substitutions

    def get_substitutions(self, ingredients: List[str]) -> Dict[str, List[str]]:
        substitutions = self._load_substitutions()
        result = {}
        for ing in ingredients:
            norm = self.matcher.normalize(ing)
            for primary, subs in substitutions.items():
                if self.matcher.is_match(norm, primary):
                    result[ing] = subs
                    break
        return result

    def find_deal_driven_substitutions(
        self,
        required_ingredients: List[Dict[str, Any]],
        active_deals: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Scans required ingredients. When an ingredient is full-price but a direct
        substitute in substitutions.json has an active high-value flyer deal,
        recommends the swap to unlock $30-$50 weekly savings.
        """
        suggested_swaps = []
        substitutions = self._load_substitutions()

        for req in required_ingredients:
            item_name = req.get("item") or req.get("name") or ""
            norm_item = self.matcher.normalize(item_name)

            # Check if original ingredient is already on sale
            on_sale = any(
                self.matcher.is_match(norm_item, d.get("product") or d.get("name", ""))
                for d in active_deals
            )
            if on_sale:
                continue

            # Check direct substitutes
            possible_subs = []
            for primary, subs in substitutions.items():
                if self.matcher.is_match(norm_item, primary):
                    possible_subs = subs
                    break

            for sub in possible_subs:
                # Find deal for substitute
                matching_deal = next(
                    (d for d in active_deals if self.matcher.is_match(sub, d.get("product") or d.get("name", ""))),
                    None
                )
                if matching_deal:
                    deal_price = matching_deal.get("price", 0.0)
                    regular_price = matching_deal.get("regular_price") or matching_deal.get("original_price") or (deal_price * 1.4)
                    savings = round(regular_price - deal_price, 2)
                    store = matching_deal.get("store", "active flyer")

                    suggested_swaps.append({
                        "original_ingredient": item_name,
                        "substitute_ingredient": sub,
                        "deal_price": deal_price,
                        "deal_store": store,
                        "estimated_savings": max(0.50, savings),
                        "reason": f"Save ${savings:.2f} by swapping {item_name} for on-sale {sub} at {store} (${deal_price:.2f})."
                    })
                    break  # One top swap per ingredient

        return suggested_swaps

substitution_service = SubstitutionService()
