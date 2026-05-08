import json
import logging
from typing import List, Dict, Any, Optional
from .models import GeneratedRecipe, Ingredient, Nutrition
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

class AIRecipeGenerator:
    """
    Generates new recipes using an LLM based on active deals.
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service or LLMService()

    def generate_recipe_from_deals(
        self,
        deals: List[Dict[str, Any]],
        user_prefs: Dict[str, Any],
        meal_type: str = "Dinner"
    ) -> GeneratedRecipe:
        """
        Calls the LLM to generate a recipe that maximizes the use of provided deals.
        """
        prompt = self._construct_prompt(deals, user_prefs, meal_type)
        system_prompt = "You are a world-class chef and budget-saving expert. You create delicious, healthy recipes that specifically use ingredients currently on sale."

        try:
            # We reuse the LLMService's call_llm which handles retries and fallback
            response_str = self.llm_service._call_llm(prompt, system_prompt=system_prompt)
            recipe_data = self.llm_service._parse_llm_response(response_str)

            # Validate and convert to Pydantic model
            return GeneratedRecipe(**recipe_data)
        except Exception as e:
            logger.error(f"Failed to generate recipe from deals: {e}")
            # Fallback mock recipe
            return self._generate_fallback_recipe(deals, meal_type)

    def _construct_prompt(self, deals: List[Dict[str, Any]], user_prefs: Dict[str, Any], meal_type: str) -> str:
        formatted_deals = json.dumps(deals[:15], indent=2) # Limit to top 15 deals
        return f"""
        Generate a {meal_type} recipe based on the following active grocery deals.
        The goal is to SAVE THE USER MONEY by using as many on-sale items as possible.

        ACTIVE DEALS:
        {formatted_deals}

        USER PREFERENCES:
        - Household Size: {user_prefs.get('household_size', 1)}
        - Dietary Restrictions: {json.dumps(user_prefs.get('dietary_preferences', []))}
        - Allergies: {json.dumps(user_prefs.get('allergies', []))}

        REQUIREMENTS:
        1. The recipe MUST be delicious and easy to prepare.
        2. Specifically highlight which ingredients are from the deals list.
        3. Provide clear instructions.
        4. Include nutritional information.

        RETURN JSON STRUCTURE:
        {{
            "name": "Recipe Name",
            "description": "Short description of why this recipe is great and budget-friendly.",
            "ingredients": [
                {{
                    "item": "Ingredient name",
                    "quantity": 2.0,
                    "unit": "lbs",
                    "is_on_sale": true,
                    "deal_description": "Save $2.00/lb at Provigo"
                }}
            ],
            "instructions": ["Step 1", "Step 2"],
            "prep_time_minutes": 30,
            "servings": {user_prefs.get('household_size', 1)},
            "nutrition": {{
                "calories": 500,
                "protein": 30,
                "carbs": 50,
                "fat": 15,
                "fiber": 5
            }},
            "cuisine": "Italian",
            "dietary_tags": ["High Protein", "Budget-friendly"]
        }}
        """

    def _generate_fallback_recipe(self, deals: List[Dict[str, Any]], meal_type: str) -> GeneratedRecipe:
        """Simple fallback recipe if LLM fails."""
        main_deal = deals[0] if deals else {"product": "Chicken", "price": 5.0}
        return GeneratedRecipe(
            name=f"Quick {main_deal.get('product')} Stir-fry",
            description="A quick and budget-friendly meal using items on sale.",
            ingredients=[
                Ingredient(item=main_deal.get('product'), quantity=1.0, unit="lb", is_on_sale=True, deal_description="On sale item")
            ],
            instructions=["Wash and chop ingredients.", "Stir-fry in a pan until cooked.", "Serve hot."],
            prep_time_minutes=20,
            servings=2,
            nutrition=Nutrition(calories=400, protein=25, carbs=20, fat=10, fiber=3),
            cuisine="General",
            dietary_tags=["Quick"]
        )
