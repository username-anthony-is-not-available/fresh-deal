
import pytest
import json
import asyncio
from unittest.mock import MagicMock, patch
from app.services.llm_service import LLMService
from datetime import datetime

def test_get_seasonal_context():
    service = LLMService()
    context = service._get_seasonal_context()
    assert "Season in Quebec" in context

    month = datetime.now().month
    if 3 <= month <= 5:
        assert "Spring" in context
        assert "maple syrup" in context
    elif 6 <= month <= 8:
        assert "Summer" in context
        assert "strawberries" in context or "strawberry" in context
    elif 9 <= month <= 11:
        assert "Autumn" in context
        assert "apples" in context or "apple" in context
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
    service._get_cached_response = MagicMock(return_value=None)
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
    service._get_cached_response = MagicMock(return_value=None)
    user_prefs = {"household_size": 2}

    # Need to ensure we don't trigger the mock AI check
    with patch("app.core.config.settings.USE_MOCK_AI", False), \
         patch("app.core.config.settings.OPENROUTER_API_KEY", "test_key"):

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


def test_sqlite_prompt_cache(tmp_path):
    service = LLMService()
    # Disable redis to test sqlite fallback
    service.redis_client = None
    service.sqlite_cache_path = str(tmp_path / "test_cache.sqlite")
    import sqlite3
    with sqlite3.connect(service.sqlite_cache_path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS prompt_cache (key TEXT PRIMARY KEY, value TEXT, expires_at REAL)")
        conn.commit()

    test_key = "test_prompt_key"
    test_data = {"meal": "test_recipe", "savings": 42.5}
    service._set_cached_response(test_key, test_data, ttl=60)
    cached = service._get_cached_response(test_key)
    assert cached == test_data


def test_ollama_local_call():
    service = LLMService()
    service.ollama_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"plan": "local_ollama_plan"}'
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    service.ollama_client.chat.completions.create.return_value = mock_resp

    with patch("app.services.llm_service.settings") as mock_settings:
        mock_settings.USE_MOCK_AI = False
        mock_settings.USE_SQLITE_LOCAL = True
        mock_settings.OPENROUTER_API_KEY = None
        mock_settings.DEFAULT_MODEL = "meta-llama/llama-3.1-8b-instruct"
        mock_settings.OLLAMA_BASE_URL = "http://localhost:11434/v1"

        res = service._call_llm("Generate meal plan", system_prompt="System instructions")
        assert res == '{"plan": "local_ollama_plan"}'
        service.ollama_client.chat.completions.create.assert_called_once()
