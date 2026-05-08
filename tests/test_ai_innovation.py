import pytest
from unittest.mock import MagicMock
from src.ai.recipe_generator import AIRecipeGenerator
from src.ai.meal_generator import AIMealGenerator
from src.ai.models import GeneratedRecipe, InnovativeMealPlan

@pytest.fixture
def mock_llm_service():
    service = MagicMock()
    # Mock LLM response for a recipe
    service._call_llm.return_value = """
    {
        "name": "Sale-Driven Chicken Pasta",
        "description": "A delicious pasta using on-sale chicken and peppers.",
        "ingredients": [
            {"item": "Chicken Breast", "quantity": 1.0, "unit": "lb", "is_on_sale": true, "deal_description": "Save $2"},
            {"item": "Bell Peppers", "quantity": 2.0, "unit": "each", "is_on_sale": true, "deal_description": "2 for $3"},
            {"item": "Pasta", "quantity": 1.0, "unit": "box", "is_on_sale": false}
        ],
        "instructions": ["Boil pasta", "Sauté chicken and peppers", "Mix and serve"],
        "prep_time_minutes": 25,
        "servings": 2,
        "nutrition": {"calories": 450, "protein": 35, "carbs": 40, "fat": 12, "fiber": 4},
        "cuisine": "Italian",
        "dietary_tags": ["High Protein"]
    }
    """
    service._parse_llm_response.side_effect = lambda x: MagicMock(__class__=dict, **eval(x)) if isinstance(x, str) and "{" in x else {}
    # Actually, let's just make it return a real dict
    import json
    service._parse_llm_response.side_effect = lambda x: json.loads(x)
    return service

def test_recipe_generation(mock_llm_service):
    generator = AIRecipeGenerator(llm_service=mock_llm_service)
    deals = [{"product": "Chicken", "discount_percent": 20}]
    user_prefs = {"household_size": 2}

    recipe = generator.generate_recipe_from_deals(deals, user_prefs)

    assert isinstance(recipe, GeneratedRecipe)
    assert recipe.name == "Sale-Driven Chicken Pasta"
    assert recipe.servings == 2
    assert any(ing.is_on_sale for ing in recipe.ingredients)

def test_meal_plan_generation(mock_llm_service):
    recipe_gen = AIRecipeGenerator(llm_service=mock_llm_service)
    meal_gen = AIMealGenerator(recipe_generator=recipe_gen)

    deals = [
        {"product": "Chicken", "discount_percent": 20},
        {"product": "Peppers", "discount_percent": 30},
        {"product": "Onions", "discount_percent": 15}
    ]
    user_prefs = {"household_size": 2}

    plan = meal_gen.generate_innovative_plan(deals, user_prefs, num_suggestions=2)

    assert isinstance(plan, InnovativeMealPlan)
    assert len(plan.suggestions) == 2
    assert plan.total_estimated_savings > 0
    assert plan.suggestions[0].recipe.name == "Sale-Driven Chicken Pasta"
