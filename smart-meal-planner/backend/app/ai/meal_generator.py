import logging
from typing import List, Dict, Any, Optional
from .models import InnovativeMealPlan, MealSuggestion
from .recipe_generator import AIRecipeGenerator

logger = logging.getLogger(__name__)

class AIMealGenerator:
    """
    Orchestrates the generation of innovative meal suggestions based on active deals.
    """

    def __init__(self, recipe_generator: Optional[AIRecipeGenerator] = None):
        self.recipe_generator = recipe_generator or AIRecipeGenerator()

    def generate_innovative_plan(
        self,
        deals: List[Dict[str, Any]],
        user_prefs: Dict[str, Any],
        num_suggestions: int = 3,
        language: str = "en"
    ) -> InnovativeMealPlan:
        """
        Generates multiple meal suggestions, each centered around key deals.
        """
        suggestions = []
        total_savings = 0.0

        sorted_deals = sorted(
            deals,
            key=lambda x: x.get('discount_percent', 0) or x.get('discount_pct', 0),
            reverse=True
        )

        for i in range(num_suggestions):
            deal_subset = sorted_deals[i*5 : (i+1)*5 + 5]
            if not deal_subset:
                deal_subset = sorted_deals[:10]

            try:
                recipe = self.recipe_generator.generate_recipe_from_deals(
                    deal_subset, user_prefs, meal_type="Dinner", language=language
                )

                on_sale_count = sum(1 for ing in recipe.ingredients if ing.is_on_sale)
                est_savings = on_sale_count * 2.50

                lead_item = deal_subset[0].get('product') or deal_subset[0].get('name', 'weekly staples') if deal_subset else 'weekly staples'
                deal_reasoning = (
                    f"Ce repas intègre {on_sale_count} articles en circulaire, axé sur {lead_item}."
                    if language.startswith("fr")
                    else f"This recipe utilizes {on_sale_count} items currently on sale, focusing on high-value discounts like {lead_item}."
                )

                suggestion = MealSuggestion(
                    recipe=recipe,
                    deal_reasoning=deal_reasoning,
                    estimated_savings=est_savings
                )
                suggestions.append(suggestion)
                total_savings += est_savings
            except Exception as e:
                logger.error(f"Error generating meal suggestion {i}: {e}")

        shopping_notes = (
            "Achetez les protéines et légumes vedettes en début de semaine pour maximiser les économies."
            if language.startswith("fr")
            else "Buy featured sale proteins and produce early in the week to maximize freshness and savings."
        )

        return InnovativeMealPlan(
            suggestions=suggestions,
            total_estimated_savings=round(total_savings, 2),
            shopping_list_notes=shopping_notes
        )
