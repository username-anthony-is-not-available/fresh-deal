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
        num_suggestions: int = 3
    ) -> InnovativeMealPlan:
        """
        Generates multiple meal suggestions, each centered around key deals.
        """
        suggestions = []
        total_savings = 0.0

        # Sort deals by discount percentage to focus on best value
        sorted_deals = sorted(deals, key=lambda x: x.get('discount_percent', 0), reverse=True)

        # Generate a few different meal suggestions
        for i in range(num_suggestions):
            # Take a slice of deals for each suggestion to ensure variety
            deal_subset = sorted_deals[i*5 : (i+1)*5 + 5]
            if not deal_subset:
                deal_subset = sorted_deals[:10]

            try:
                recipe = self.recipe_generator.generate_recipe_from_deals(
                    deal_subset, user_prefs, meal_type="Dinner"
                )

                # Calculate estimated savings for this suggestion
                on_sale_count = sum(1 for ing in recipe.ingredients if ing.is_on_sale)
                est_savings = on_sale_count * 2.50 # Rough heuristic for savings per deal item

                suggestion = MealSuggestion(
                    recipe=recipe,
                    deal_reasoning=f"This recipe utilizes {on_sale_count} items currently on sale, focusing on high-value discounts like {deal_subset[0].get('product') if deal_subset else 'various items'}.",
                    estimated_savings=est_savings
                )
                suggestions.append(suggestion)
                total_savings += est_savings
            except Exception as e:
                logger.error(f"Error generating meal suggestion {i}: {e}")

        return InnovativeMealPlan(
            suggestions=suggestions,
            total_estimated_savings=round(total_savings, 2),
            shopping_list_notes="These meals were designed to maximize your savings based on this week's flyer deals. Make sure to check the specific stores mentioned in the ingredients."
        )
