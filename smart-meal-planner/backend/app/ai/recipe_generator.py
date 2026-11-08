import json
import logging
from typing import List, Dict, Any, Optional
from .models import GeneratedRecipe, Ingredient, Nutrition
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

class AIRecipeGenerator:
    """
    Generates new recipes using an LLM based on active deals.
    Specialized for Quebec grocery staples (pork tenderloin, medium ground beef,
    chicken thighs, root vegetables, Halloumi/Adonis specials, etc.).
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service or LLMService()

    def generate_recipe_from_deals(
        self,
        deals: List[Dict[str, Any]],
        user_prefs: Dict[str, Any],
        meal_type: str = "Dinner",
        language: str = "en"
    ) -> GeneratedRecipe:
        """
        Calls the LLM to generate a recipe that maximizes the use of provided deals.
        Supports both French ('fr') and English ('en').
        """
        prompt = self._construct_prompt(deals, user_prefs, meal_type, language)
        system_prompt = (
            "You are a world-class chef and budget-saving expert in Quebec, Canada. "
            "You create delicious, healthy recipes that specifically use ingredients currently on sale at Quebec grocers. "
            "Return valid JSON matching the GeneratedRecipe schema."
        )

        try:
            response_str = self.llm_service._call_llm(prompt, system_prompt=system_prompt)
            recipe_data = self.llm_service._parse_llm_response(response_str)
            return GeneratedRecipe(**recipe_data)
        except Exception as e:
            logger.error(f"Failed to generate recipe from deals: {e}")
            return self._generate_fallback_recipe(deals, meal_type, language)

    def _construct_prompt(
        self, deals: List[Dict[str, Any]], user_prefs: Dict[str, Any], meal_type: str, language: str = "en"
    ) -> str:
        formatted_deals = json.dumps(deals[:15], indent=2)
        lang_instruction = "Respond entirely in French." if language.startswith("fr") else "Respond in English."
        return f"""
        Generate a {meal_type} recipe based on the following active grocery deals in Quebec.
        The goal is to SAVE THE USER MONEY by using as many on-sale items as possible.
        {lang_instruction}

        ACTIVE DEALS:
        {formatted_deals}

        USER PREFERENCES:
        - Household Size: {user_prefs.get('household_size', 2)}
        - Dietary Preferences: {user_prefs.get('dietary_preferences', 'None')}
        - Allergies: {user_prefs.get('allergies', 'None')}

        JSON FORMAT SPECIFICATION:
        {{
            "name": "Recipe Name",
            "description": "Short description mentioning flyer savings",
            "ingredients": [
                {{
                    "item": "Name of ingredient",
                    "quantity": 1.5,
                    "unit": "lbs",
                    "is_on_sale": true,
                    "deal_description": "On sale at Metro for $4.99/lb"
                }}
            ],
            "instructions": ["Step 1", "Step 2"],
            "prep_time_minutes": 30,
            "servings": {user_prefs.get('household_size', 2)},
            "nutrition": {{
                "calories": 500,
                "protein": 30,
                "carbs": 40,
                "fat": 15,
                "fiber": 5
            }},
            "cuisine": "Quebec Comfort",
            "dietary_tags": ["Budget-Friendly"]
        }}
        """

    def _generate_fallback_recipe(
        self, deals: List[Dict[str, Any]], meal_type: str, language: str = "en"
    ) -> GeneratedRecipe:
        is_fr = language.startswith("fr")
        top_deal = deals[0] if deals else {"product": "Chicken Breast", "price": 4.99}
        deal_name = top_deal.get("product") or top_deal.get("name", "Chicken Breast")

        if is_fr:
            return GeneratedRecipe(
                name=f"Sauté de {deal_name} aux légumes de saison",
                description="Un repas économique et savoureux préparé avec les rabais de la semaine.",
                ingredients=[
                    Ingredient(item=deal_name, quantity=1.0, unit="lb", is_on_sale=True, deal_description="En circulaire"),
                    Ingredient(item="Légumes mélangés", quantity=2.0, unit="tasses", is_on_sale=False),
                    Ingredient(item="Riz blanc", quantity=1.0, unit="tasse", is_on_sale=False),
                ],
                instructions=[
                    "Cuire le riz selon les instructions sur l'emballage.",
                    f"Faire dorer le {deal_name} dans une poêle chaude.",
                    "Ajouter les légumes et faire sauter pendant 5 à 7 minutes.",
                    "Servir chaud sur un lit de riz.",
                ],
                prep_time_minutes=25,
                servings=2,
                nutrition=Nutrition(calories=480, protein=38, carbs=45, fat=12, fiber=4),
                cuisine="Québécoise",
                dietary_tags=["Économique", "Riche en protéines"],
            )
        else:
            return GeneratedRecipe(
                name=f"Skillet {deal_name} with Seasonal Veggies",
                description="A budget-friendly meal highlighting active weekly flyer discounts.",
                ingredients=[
                    Ingredient(item=deal_name, quantity=1.0, unit="lb", is_on_sale=True, deal_description="Weekly deal"),
                    Ingredient(item="Mixed Vegetables", quantity=2.0, unit="cups", is_on_sale=False),
                    Ingredient(item="White Rice", quantity=1.0, unit="cup", is_on_sale=False),
                ],
                instructions=[
                    "Cook rice according to package directions.",
                    f"Sear {deal_name} in a hot skillet until cooked through.",
                    "Toss in vegetables and sauté for 5-7 minutes.",
                    "Serve warm over rice.",
                ],
                prep_time_minutes=25,
                servings=2,
                nutrition=Nutrition(calories=480, protein=38, carbs=45, fat=12, fiber=4),
                cuisine="Quick & Easy",
                dietary_tags=["Budget-Friendly", "High Protein"],
            )
