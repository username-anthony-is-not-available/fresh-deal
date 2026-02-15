
import pytest
import json
from unittest.mock import MagicMock, patch
from app.services.llm_service import LLMService

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

import asyncio

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
