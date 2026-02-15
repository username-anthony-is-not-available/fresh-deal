
import pytest
import json
import asyncio
from unittest.mock import MagicMock, patch
from app.services.llm_service import LLMService
from datetime import datetime

def test_get_seasonal_context():
    service = LLMService()
    context = service._get_seasonal_context()
    assert "Current Season in Quebec" in context

    month = datetime.now().month
    if 3 <= month <= 5:
        assert "Spring" in context
        assert "maple syrup" in context
    elif 6 <= month <= 8:
        assert "Summer" in context
        assert "strawberries" in context
    elif 9 <= month <= 11:
        assert "Autumn" in context
        assert "apples" in context
    else:
        assert "Winter" in context
        assert "root vegetables" in context

def test_construct_system_prompt_no_restrictions():
    service = LLMService()
    prompt = service._construct_system_prompt([], [])
    assert "You are a helpful meal planning assistant that outputs valid JSON." == prompt

def test_construct_system_prompt_with_dietary():
    service = LLMService()
    prompt = service._construct_system_prompt(["gluten-free", "vegan"], [])
    assert "CRITICAL: The user has the following dietary restrictions: Dietary preferences: gluten-free, vegan." in prompt
    assert "You MUST ensure" in prompt

def test_construct_system_prompt_with_allergies():
    service = LLMService()
    prompt = service._construct_system_prompt([], ["peanuts", "shellfish"])
    assert "CRITICAL: The user has the following dietary restrictions: Allergies to avoid: peanuts, shellfish." in prompt
    assert "You MUST ensure" in prompt

def test_construct_system_prompt_with_both():
    service = LLMService()
    prompt = service._construct_system_prompt(["vegan"], ["soy"])
    assert "Dietary preferences: vegan" in prompt
    assert "Allergies to avoid: soy" in prompt

@patch("app.services.llm_service.LLMService._call_llm")
def test_generate_meal_plan_passes_system_prompt(mock_call_llm):
    service = LLMService()
    user_prefs = {
        "household_size": 2,
        "dietary_preferences": ["gluten-free"],
        "allergies": ["dairy"]
    }

    # Mocking necessary methods called before _call_llm
    service.get_next_week_dates = MagicMock(return_value=[{"date": "2023-01-01"}]*7)
    service._construct_meal_plan_prompt = MagicMock(return_value="User Prompt")
    service._parse_llm_response = MagicMock(return_value={"meal_plan": []})

    service.generate_meal_plan(user_prefs, [], [])

    # Check if _call_llm was called with a system prompt containing our restrictions
    args, kwargs = mock_call_llm.call_args
    system_prompt = kwargs.get("system_prompt")
    assert system_prompt is not None
    assert "gluten-free" in system_prompt
    assert "dairy" in system_prompt

@patch("app.services.llm_service.LLMService._make_api_request")
def test_generate_meal_plan_with_model_type(mock_make_request):
    mock_make_request.return_value = json.dumps({"meal_plan": []})
    service = LLMService()
    user_prefs = {"household_size": 2}

    # Test with 'chef' model
    service.generate_meal_plan(user_prefs, [], [], model_type="chef")

    # Check if _make_api_request was called with the mapped model ID for 'chef'
    args, _ = mock_make_request.call_args
    assert args[0] == service.MODEL_MAPPING["chef"]

@pytest.mark.asyncio
@patch("app.services.llm_service.LLMService._call_llm")
async def test_regenerate_single_meal_passes_system_prompt(mock_call_llm):
    # Mock session
    mock_session = MagicMock()

    with patch("app.services.llm_service.RecipeService") as mock_recipe_service_class, \
         patch("app.services.llm_service.DealService") as mock_deal_service_class:

        mock_recipe_service = mock_recipe_service_class.return_value

        # Async mock for get_all_recipes_as_dicts
        f_recipes = asyncio.Future()
        f_recipes.set_result([])
        mock_recipe_service.get_all_recipes_as_dicts.return_value = f_recipes

        mock_recipe_service.filter_recipes.return_value = [{"id": 1}] # Need at least one to not return None early

        mock_deal_service = mock_deal_service_class.return_value
        f_deals = asyncio.Future()
        f_deals.set_result([])
        mock_deal_service.get_active_deals_as_dicts.return_value = f_deals

        service = LLMService()
        user = MagicMock()
        user.household_size = 1
        user.allergies = ["nuts"]

        service._construct_regenerate_meal_prompt = MagicMock(return_value="User Prompt")
        service._parse_llm_response = MagicMock(return_value={"breakfast": {}})

        await service.regenerate_single_meal(
            user=user,
            day="Monday",
            meal_type="Breakfast",
            dietary_preferences=["vegan"],
            existing_meals=[],
            session=mock_session
        )

        args, kwargs = mock_call_llm.call_args
        system_prompt = kwargs.get("system_prompt")
        assert system_prompt is not None
        assert "vegan" in system_prompt
        assert "nuts" in system_prompt
