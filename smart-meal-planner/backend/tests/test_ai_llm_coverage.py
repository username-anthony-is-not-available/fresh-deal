"""Coverage for app/ai/meal_generator.py, app/ai/recipe_generator.py and
app/services/llm_service.py. The LLM client is faked; the SQLite prompt
cache is built in a tmp dir (LLMService writes .cache under the cwd).
"""

import json
import sqlite3
import time
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import APIError

from app.ai.meal_generator import AIMealGenerator
from app.ai.recipe_generator import AIRecipeGenerator
from app.ai.models import GeneratedRecipe, Ingredient, Nutrition
from app.services.llm_service import LLMService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _recipe(name="Test Recipe", on_sale=2):
    return GeneratedRecipe(
        name=name,
        description="desc",
        ingredients=[
            Ingredient(item="Chicken", quantity=1.0, unit="lb", is_on_sale=True),
            Ingredient(item="Rice", quantity=1.0, unit="cup", is_on_sale=True),
            Ingredient(item="Salt", quantity=1.0, unit="tsp", is_on_sale=False),
        ][: on_sale + 1],
        instructions=["Cook it."],
        prep_time_minutes=20,
        servings=2,
        nutrition=Nutrition(calories=400, protein=20, carbs=30, fat=10, fiber=5),
        cuisine="Test",
        dietary_tags=[],
    )


class _FakeLLM:
    """Fake LLMService for the recipe generator."""

    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc

    def _call_llm(self, prompt, system_prompt=None):
        if self._exc is not None:
            raise self._exc
        return self._response

    def _parse_llm_response(self, response_str):
        return json.loads(response_str)


@pytest.fixture
def llm_service(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    svc = LLMService()
    assert svc.redis_client is None  # no Redis in this environment
    assert svc.sqlite_cache_path is not None
    return svc


# ---------------------------------------------------------------------------
# AIMealGenerator
# ---------------------------------------------------------------------------

def test_meal_generator_sorts_and_sums_savings():
    gen = AIRecipeGenerator(llm_service=_FakeLLM(response=json.dumps(_recipe().model_dump())))
    plan = AIMealGenerator(recipe_generator=gen).generate_innovative_plan(
        deals=[
            {"product": "Cheap", "discount_pct": 10},
            {"product": "Best", "discount_percent": 50},
            {"product": "Mid", "discount_pct": 30},
        ],
        user_prefs={"household_size": 2},
        num_suggestions=2,
    )
    assert len(plan.suggestions) == 2
    assert plan.suggestions[0].deal_reasoning.startswith("This recipe utilizes")
    # 2 on-sale ingredients per recipe -> 2 * $2.50 each
    assert plan.total_estimated_savings == 10.0
    assert "freshness" in plan.shopping_list_notes


def test_meal_generator_french_and_empty_deals():
    gen = AIRecipeGenerator(llm_service=_FakeLLM(response=json.dumps(_recipe().model_dump())))
    plan = AIMealGenerator(recipe_generator=gen).generate_innovative_plan(
        deals=[], user_prefs={}, num_suggestions=1, language="fr"
    )
    assert len(plan.suggestions) == 1
    assert "circulaire" in plan.suggestions[0].deal_reasoning
    assert plan.suggestions[0].estimated_savings == 5.0
    assert "semaine" in plan.shopping_list_notes


def test_meal_generator_generator_failure_skips_suggestion():
    class _Boom:
        def generate_recipe_from_deals(self, *a, **k):
            raise RuntimeError("boom")

    plan = AIMealGenerator(recipe_generator=_Boom()).generate_innovative_plan(
        deals=[{"product": "X", "discount_pct": 10}], user_prefs={}, num_suggestions=2
    )
    assert plan.suggestions == []
    assert plan.total_estimated_savings == 0.0


def test_meal_generator_default_recipe_generator():
    # Default constructor builds a real AIRecipeGenerator (with a real LLMService).
    gen = AIMealGenerator()
    assert isinstance(gen.recipe_generator, AIRecipeGenerator)


# ---------------------------------------------------------------------------
# AIRecipeGenerator
# ---------------------------------------------------------------------------

def test_recipe_generator_llm_success():
    recipe = _recipe()
    gen = AIRecipeGenerator(llm_service=_FakeLLM(response=json.dumps(recipe.model_dump())))
    out = gen.generate_recipe_from_deals(
        [{"product": "Chicken", "price": 4.99}], {"household_size": 4}, language="en"
    )
    assert out.name == "Test Recipe"
    assert out.servings == 2


def test_recipe_generator_llm_failure_falls_back_en_and_fr():
    gen = AIRecipeGenerator(llm_service=_FakeLLM(exc=RuntimeError("no llm")))
    en = gen.generate_recipe_from_deals(
        [{"product": "Pork", "price": 3.99}], {}, meal_type="Lunch", language="en"
    )
    assert en.name == "Skillet Pork with Seasonal Veggies"
    assert en.cuisine == "Quick & Easy"
    fr = gen.generate_recipe_from_deals(
        [{"name": "Poulet", "price": 3.99}], {}, meal_type="Dîner", language="fr"
    )
    assert "Sauté de Poulet" in fr.name
    assert fr.cuisine == "Québécoise"


def test_recipe_generator_fallback_no_deals():
    gen = AIRecipeGenerator(llm_service=_FakeLLM(exc=RuntimeError("no llm")))
    out = gen.generate_recipe_from_deals([], {})
    assert "Chicken Breast" in out.name


def test_recipe_generator_construct_prompt_fr():
    gen = AIRecipeGenerator(llm_service=_FakeLLM())
    prompt = gen._construct_prompt(
        [{"product": "A"}] * 20, {"household_size": 3}, meal_type="Breakfast", language="fr"
    )
    assert "Respond entirely in French." in prompt
    assert '"household_size": 3' not in prompt  # prefs are inlined, not dumped
    assert "Household Size: 3" in prompt
    # Only the first 15 deals are embedded.
    assert prompt.count('"product": "A"') == 15


def test_recipe_generator_default_llm_service():
    assert isinstance(AIRecipeGenerator().llm_service, LLMService)


# ---------------------------------------------------------------------------
# LLMService — cache, prompts, formatting
# ---------------------------------------------------------------------------

def test_llm_cache_key_deterministic(llm_service):
    k1 = llm_service._get_cache_key("meal_plan", {"a": 1, "b": 2})
    k2 = llm_service._get_cache_key("meal_plan", {"b": 2, "a": 1})
    assert k1 == k2
    assert k1.startswith("meal_plan:")


def test_llm_sqlite_cache_roundtrip_and_expiry(llm_service):
    key = llm_service._get_cache_key("test", {"x": 1})
    assert llm_service._get_cached_response(key) is None
    llm_service._set_cached_response(key, {"plan": True}, ttl=3600)
    assert llm_service._get_cached_response(key) == {"plan": True}
    # Expired entries are deleted and return None.
    expired_key = llm_service._get_cache_key("test", {"x": 2})
    with sqlite3.connect(llm_service.sqlite_cache_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO prompt_cache VALUES (?, ?, ?)",
            (expired_key, json.dumps({"old": True}), time.time() - 10),
        )
        conn.commit()
    assert llm_service._get_cached_response(expired_key) is None
    with sqlite3.connect(llm_service.sqlite_cache_path) as conn:
        row = conn.execute(
            "SELECT * FROM prompt_cache WHERE key = ?", (expired_key,)
        ).fetchone()
    assert row is None


def test_llm_redis_cache_and_errors(llm_service):
    key = "redis:key"
    fake_redis = MagicMock()
    fake_redis.get.return_value = json.dumps({"from": "redis"})
    llm_service.redis_client = fake_redis
    assert llm_service._get_cached_response(key) == {"from": "redis"}
    llm_service._set_cached_response(key, {"v": 1})
    fake_redis.setex.assert_called_once()
    # A Redis error falls through to SQLite (which already holds {"v": 1}
    # from the earlier set, since _set_cached_response writes both stores).
    fake_redis.get.side_effect = RuntimeError("redis down")
    fake_redis.setex.side_effect = RuntimeError("redis down")
    assert llm_service._get_cached_response(key) == {"v": 1}
    llm_service._set_cached_response(key, {"v": 2})
    assert llm_service._get_cached_response(key) == {"v": 2}


def test_llm_construct_system_prompt(llm_service):
    assert "Dietary preferences" not in llm_service._construct_system_prompt()
    with_prefs = llm_service._construct_system_prompt(["vegan"], [])
    assert "Dietary preferences: vegan" in with_prefs
    assert "CRITICAL" in with_prefs
    with_both = llm_service._construct_system_prompt(["vegan"], ["peanuts"])
    assert "Allergies to avoid: peanuts" in with_both


def test_llm_format_deals(llm_service):
    deals = [
        {"product": "A", "price": 5.0, "discount": 10},
        {"product": "B", "price": 2.0, "discount": 50, "regular_price": 4.0,
         "expires_in_days": 1, "unit": "kg", "store": "Metro", "category": "Meat"},
    ]
    out = json.loads(llm_service.format_deals_for_llm(deals))
    assert out[0]["product"] == "B"  # sorted by discount desc
    assert out[0]["regular_price"] == 4.0
    assert out[1]["regular_price"] == 7.5  # default: price * 1.5
    assert out[1]["category"] == "general"
    many = [{"product": f"P{i}", "price": 1.0, "discount": i} for i in range(40)]
    assert len(json.loads(llm_service.format_deals_for_llm(many))) == 30


def test_llm_next_week_dates(llm_service):
    dates = llm_service.get_next_week_dates()
    assert len(dates) == 7
    assert dates[0]["day_name"] == "Monday"
    assert [d["day"] for d in dates] == list(range(1, 8))
    parsed = [datetime.strptime(d["date"], "%Y-%m-%d") for d in dates]
    assert all((parsed[i + 1] - parsed[i]).days == 1 for i in range(6))


def test_llm_next_week_dates_monday(llm_service):
    class _MondayDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 23)  # a Monday

    with patch("app.services.llm_service.datetime", _MondayDatetime):
        dates = llm_service.get_next_week_dates()
    # Today is Monday -> the plan starts NEXT Monday.
    assert dates[0]["date"] == "2026-11-30"
    assert dates[0]["day_name"] == "Monday"


def test_llm_init_no_ollama(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "")
    svc = LLMService()
    assert svc.ollama_client is None


def test_llm_init_sqlite_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("app.services.llm_service.sqlite3.connect",
               side_effect=RuntimeError("disk full")):
        svc = LLMService()
    assert svc.sqlite_cache_path is None
    assert svc._get_cached_response("k") is None
    svc._set_cached_response("k", {"v": 1})  # no raise


def test_llm_sqlite_cache_errors(llm_service):
    with patch("app.services.llm_service.sqlite3.connect",
               side_effect=RuntimeError("disk full")):
        assert llm_service._get_cached_response("k") is None
        llm_service._set_cached_response("k", {"v": 1})  # no raise


def test_llm_parse_response(llm_service):
    assert llm_service._parse_llm_response('{"a": 1}') == {"a": 1}
    assert llm_service._parse_llm_response('prefix {"a": 2} suffix') == {"a": 2}
    with pytest.raises(ValueError):
        llm_service._parse_llm_response("no json here")


def test_llm_format_recipes(llm_service):
    recipes = [
        {"id": 1, "name": "A", "ingredients": '[{"item": "Rice"}]',
         "allergens": '["peanuts"]', "dietary_tags": '["vegan"]',
         "nutrition": {"calories": 100}, "meal_type": "Dinner"},
        {"id": 2, "name": "B", "ingredients": [{"item": "Pasta"}],
         "allergens": ["dairy"], "dietary_tags": ["keto"],
         "nutrition": {}, "meal_type": "Lunch"},
        {"id": 3, "name": "C", "ingredients": "{bad json",
         "allergens": "{bad", "dietary_tags": "{bad"},
    ]
    out = llm_service._format_recipes_for_prompt(recipes)
    assert out[0]["ingredients"] == [{"item": "Rice"}]
    assert out[0]["allergens"] == ["peanuts"]
    assert out[0]["nutrition"] == {
        "calories": 100, "protein": None, "carbs": None, "fat": None, "fiber": None,
    }
    assert out[1]["ingredients"] == ["Pasta"]
    assert out[2]["ingredients"] == []
    assert out[2]["allergens"] == []
    assert out[2]["meal_type"] == "Any"


def test_llm_mock_plan(llm_service):
    recipes = [
        {"id": 1, "name": "Vegan Soup", "dietary_tags": ["vegan"], "meal_type": "Dinner"},
        {"id": 2, "name": "Steak", "dietary_tags": [], "meal_type": "Dinner"},
    ]
    week = llm_service.get_next_week_dates()
    plan = llm_service._generate_mock_plan(
        {"dietary_preferences": ["vegan"], "household_size": 3}, recipes, week
    )
    assert len(plan["meal_plan"]) == 7
    assert plan["meal_plan"][0]["dinner"]["recipe_name"] == "Vegan Soup"
    assert plan["shopping_summary"]["household_size"] == 3
    # No recipe matches at all -> falls back to every recipe.
    plan2 = llm_service._generate_mock_plan(
        {"dietary_preferences": ["keto"], "household_size": 1}, recipes, week
    )
    assert plan2["meal_plan"][0]["dinner"]["recipe_name"] in ("Vegan Soup", "Steak")
    # No recipes at all -> days exist with empty meals.
    plan3 = llm_service._generate_mock_plan({"household_size": 1}, [], week)
    assert plan3["meal_plan"][0]["breakfast"] is None


def test_llm_mock_single_meal(llm_service, monkeypatch):
    # _generate_mock_single_meal picks with random.choice over all
    # meal-type matches plus "Any" recipes; pin the choice so the test is
    # deterministic.
    monkeypatch.setattr("random.choice", lambda seq: seq[0])
    recipes = [
        {"id": 1, "name": "Soup", "meal_type": "Lunch"},
        {"id": 2, "name": "Anything", "meal_type": "Any"},
    ]
    meal = llm_service._generate_mock_single_meal("Lunch", recipes)
    assert meal["recipe_name"] == "Mock Lunch: Soup"
    meal2 = llm_service._generate_mock_single_meal("Breakfast", recipes)
    assert meal2["recipe_name"] == "Mock Breakfast: Anything"
    assert llm_service._generate_mock_single_meal("Dinner", []) is None


def test_llm_seasonal_context(llm_service):
    ctx = llm_service._get_seasonal_context()
    assert "Season in Quebec:" in ctx
    assert "Current Month:" in ctx


@pytest.mark.parametrize("month,season", [
    (4, "Spring"), (7, "Summer"), (10, "Autumn"), (1, "Winter"),
])
def test_llm_seasonal_context_all_seasons(llm_service, month, season):
    # _get_seasonal_context reads datetime.now() from its own module namespace.
    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, month, 15)

    with patch("app.services.llm_service.datetime", _FixedDatetime):
        ctx = llm_service._get_seasonal_context()
    assert f"Season in Quebec: {season}." in ctx


# ---------------------------------------------------------------------------
# LLMService — API calls
# ---------------------------------------------------------------------------

class _FakeCompletions:
    def __init__(self, fn):
        self._fn = fn

    def create(self, **kwargs):
        return self._fn(**kwargs)


class _FakeClient:
    def __init__(self, fn):
        self.chat = SimpleNamespace(completions=_FakeCompletions(fn))


def _completion(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def test_llm_make_api_request_success(llm_service):
    client = _FakeClient(lambda **kw: _completion('{"ok": true}'))
    assert llm_service._make_api_request("model", "prompt", client=client) == '{"ok": true}'


def test_llm_make_api_request_empty_content(llm_service):
    client = _FakeClient(lambda **kw: _completion(None))
    with pytest.raises(ValueError, match="Empty response"):
        llm_service._make_api_request("model", "prompt", client=client)


def test_llm_make_api_request_retries_rate_limit(llm_service):
    from openai import RateLimitError

    calls = {"n": 0}

    def flaky(**kw):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RateLimitError("slow down", response=MagicMock(), body=None)
        return _completion("recovered")

    client = _FakeClient(flaky)
    assert llm_service._make_api_request("model", "prompt", client=client) == "recovered"
    assert calls["n"] == 2


def test_llm_call_mock_ai_raises(llm_service, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "USE_MOCK_AI", True)
    with pytest.raises(APIError):
        llm_service._call_llm("prompt")


def test_llm_call_ollama_then_openrouter(llm_service, monkeypatch):
    from app.core.config import settings

    # The dev .env enables mock AI; the dispatch paths need it off.
    monkeypatch.setattr(settings, "USE_MOCK_AI", False)

    # Ollama succeeds.
    with patch.object(llm_service, "_make_api_request", return_value="ollama-ok") as m:
        assert llm_service._call_llm("prompt") == "ollama-ok"
        assert m.call_args.kwargs["client"] is llm_service.ollama_client
    # Ollama fails, no OpenRouter key -> APIError.
    with patch.object(llm_service, "_make_api_request", side_effect=RuntimeError("down")):
        with pytest.raises(APIError):
            llm_service._call_llm("prompt")
    # With an OpenRouter key, primary succeeds; fallback used when primary fails.
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "key")
    with patch.object(llm_service, "_make_api_request", side_effect=[RuntimeError("down"), "fallback-ok"]) as m:
        assert llm_service._call_llm("prompt") == "fallback-ok"
        assert m.call_count == 2
    # Both models fail -> APIError.
    with patch.object(llm_service, "_make_api_request", side_effect=RuntimeError("down")):
        with pytest.raises(APIError):
            llm_service._call_llm("prompt")


def test_llm_generate_meal_plan_cached_and_mock(llm_service):
    prefs = {"household_size": 2}
    recipes = [{"id": 1, "name": "Soup", "meal_type": "Any", "dietary_tags": []}]
    cached = {"meal_plan": [], "cached": True}
    with patch.object(llm_service, "_get_cached_response", return_value=cached):
        assert llm_service.generate_meal_plan(prefs, [], recipes) is cached
    with patch.object(llm_service, "_get_cached_response", return_value=None), \
         patch.object(llm_service, "_call_llm", return_value='{"meal_plan": []}'):
        plan = llm_service.generate_meal_plan(prefs, [], recipes)
        assert plan == {"meal_plan": []}
    with patch.object(llm_service, "_get_cached_response", return_value=None), \
         patch.object(llm_service, "_call_llm", side_effect=RuntimeError("llm down")):
        plan = llm_service.generate_meal_plan(prefs, [], recipes)
        assert len(plan["meal_plan"]) == 7  # mock fallback


@pytest.mark.asyncio
async def test_llm_regenerate_single_meal(llm_service):
    from app.services.deal_service import DealService
    from app.services.recipe_service import RecipeService

    user = SimpleNamespace(id=1, household_size=2, allergies=[])
    recipes = [{"id": 1, "name": "Soup", "dietary_tags": [], "meal_type": "Lunch"}]
    with patch.object(RecipeService, "get_all_recipes_as_dicts",
                      new=AsyncMock(return_value=recipes)), \
         patch.object(DealService, "get_active_deals_as_dicts",
                      new=AsyncMock(return_value=[])), \
         patch.object(llm_service, "_call_llm",
                      return_value='{"lunch": {"recipe_id": 1, "recipe_name": "Soup"}}'):
        meal = await llm_service.regenerate_single_meal(
            user, "Monday", "Lunch", [], [], MagicMock()
        )
        assert meal == {"recipe_id": 1, "recipe_name": "Soup"}


@pytest.mark.asyncio
async def test_llm_regenerate_single_meal_no_safe_recipes(llm_service):
    from app.services.deal_service import DealService
    from app.services.recipe_service import RecipeService

    user = SimpleNamespace(id=1, household_size=2, allergies=[])
    with patch.object(RecipeService, "get_all_recipes_as_dicts",
                      new=AsyncMock(return_value=[])), \
         patch.object(DealService, "get_active_deals_as_dicts",
                      new=AsyncMock(return_value=[])):
        assert await llm_service.regenerate_single_meal(
            user, "Monday", "Lunch", [], [], MagicMock()
        ) is None


@pytest.mark.asyncio
async def test_llm_regenerate_single_meal_llm_failure_mock(llm_service):
    from app.services.deal_service import DealService
    from app.services.recipe_service import RecipeService

    user = SimpleNamespace(id=1, household_size=2, allergies=[])
    recipes = [{"id": 1, "name": "Soup", "dietary_tags": [], "meal_type": "Lunch"}]
    with patch.object(RecipeService, "get_all_recipes_as_dicts",
                      new=AsyncMock(return_value=recipes)), \
         patch.object(DealService, "get_active_deals_as_dicts",
                      new=AsyncMock(return_value=[])), \
         patch.object(llm_service, "_call_llm", side_effect=RuntimeError("down")):
        meal = await llm_service.regenerate_single_meal(
            user, "Monday", "Lunch", [], [], MagicMock()
        )
        assert meal["recipe_name"] == "Mock Lunch: Soup"


def test_llm_construct_regenerate_meal_prompt(llm_service):
    user = SimpleNamespace(household_size=4)
    prompt = llm_service._construct_regenerate_meal_prompt(
        user, "Tuesday", "Dinner", ["vegan"],
        [{"recipe_name": "Old Soup"}, {"name": "Old Salad"}],
        [{"id": 1, "name": "New"}],
        [{"product": "Chicken", "price": 5.0}],
    )
    assert "Tuesday" in prompt and "Dinner" in prompt
    assert "Old Soup" in prompt and "Old Salad" in prompt
    assert "Household Size: 4" in prompt
