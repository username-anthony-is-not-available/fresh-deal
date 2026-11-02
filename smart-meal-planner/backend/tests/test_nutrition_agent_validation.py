import asyncio
from unittest.mock import AsyncMock

import pytest


@pytest.mark.parametrize(
    "meal_plan",
    [
        pytest.param(None, id="missing"),
        pytest.param([], id="empty"),
        pytest.param("", id="empty-non-list"),
        pytest.param({"invalid": "shape"}, id="unsupported-shape"),
    ],
)
def test_validate_plan_uses_days_when_meal_plan_is_missing_empty_or_invalid(
    meal_plan, monkeypatch
):
    monkeypatch.setenv("USE_MOCK_AI", "True")
    from app.agents.nutrition_agent import NutritionAgent

    agent = NutritionAgent()
    estimate = AsyncMock(
        return_value={"calories": 600, "protein": 30, "carbs": 75, "fat": 20}
    )
    monkeypatch.setattr(agent, "estimate_meal_nutrition", estimate)

    meal = {"name": "Chicken rice", "ingredients": ["chicken", "rice"]}
    plan = {"days": [{"meals": [meal]}]}
    if meal_plan is not None:
        plan["meal_plan"] = meal_plan

    result = asyncio.run(agent.validate_plan(plan))

    estimate.assert_awaited_once_with("Chicken rice", ["chicken", "rice"])
    assert meal["nutrition"] == {
        "calories": 600,
        "protein": 30,
        "carbs": 75,
        "fat": 20,
    }
    assert result["days"][0]["daily_summary"] == {
        "calories": 600,
        "protein": 30,
        "carbs": 75,
        "fat": 20,
    }
    assert result["nutritional_summary"] == {
        "avg_daily_calories": 600,
        "avg_daily_protein": 30,
        "total_weekly_calories": 600,
        "total_weekly_protein": 30,
        "total_weekly_carbs": 75,
        "total_weekly_fat": 20,
        "note": "Nutritional information is an estimate.",
    }


def test_validate_plan_leaves_unsupported_plan_unchanged(monkeypatch):
    monkeypatch.setenv("USE_MOCK_AI", "True")
    from app.agents.nutrition_agent import NutritionAgent

    plan = {"meal_plan": {"breakfast": {"name": "Oatmeal"}}}

    assert asyncio.run(NutritionAgent().validate_plan(plan)) is plan


def test_validate_plan_leaves_non_dictionary_days_unchanged(monkeypatch):
    monkeypatch.setenv("USE_MOCK_AI", "True")
    from app.agents.nutrition_agent import NutritionAgent

    plan = {"days": [None]}

    assert asyncio.run(NutritionAgent().validate_plan(plan)) is plan
