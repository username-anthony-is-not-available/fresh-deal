"""Tests for meal plan nutritional calculations and persistence (Issue #387)."""

from datetime import date, datetime, timezone
import json
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel, select

from app.agents.nutrition_agent import NutritionAgent
from app.models.all_models import DailyNutrition, MealPlan, Recipe, User
from app.services.user_service import UserService


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_user_service_nutrition_summary_supports_days_meals_inline_and_fats(async_session: AsyncSession):
    """UserService should compute accurate totals across 'days', 'meals', 'snacks', inline nutrition, and 'fats'."""
    user = User(email="calc@example.com", hashed_password="pw", postal_code="H4T1V6", household_size=2)
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)

    db_recipe = Recipe(
        name="DB Chicken Bowl",
        ingredients_json=json.dumps(["chicken", "rice"]),
        instructions_json=json.dumps(["Cook"]),
        nutrition_json=json.dumps({"calories": 550.5, "protein": 42, "carbs": 50, "fats": 14, "fiber": 6}),
    )
    async_session.add(db_recipe)
    await async_session.commit()
    await async_session.refresh(db_recipe)

    plan_payload = {
        "days": [
            {
                "date": "2026-11-10",
                "meals": [
                    {"recipe_id": db_recipe.id, "name": "DB Chicken Bowl"},
                    {
                        "name": "Greek Yogurt",
                        "nutrition": {"calories": 150.5, "protein": 15, "carbs": 12, "fat": 4, "fiber": None},
                    },
                ],
            },
            {
                "date": "2026-11-11",
                "breakfast": {"name": "Oatmeal", "nutrition": {"calories": 320, "protein": 10, "carbs": 54, "fats": 6, "fiber": 8}},
                "snacks": [
                    {"name": "Apple", "nutrition": {"calories": 95, "protein": 0.5, "carbs": 25, "fat": 0.3, "fiber": 4}}
                ],
            },
        ]
    }
    meal_plan = MealPlan(
        user_id=user.id,
        start_date=date(2026, 11, 10),
        end_date=date(2026, 11, 11),
        content_json=json.dumps(plan_payload),
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    async_session.add(meal_plan)
    await async_session.commit()

    service = UserService(async_session)
    summary = await service.get_meal_plan_nutrition_summary(user.id)

    assert summary["totals"] == {
        "calories": 1116.0,
        "protein": 67.5,
        "carbs": 141.0,
        "fat": 24.3,
        "fiber": 18.0,
    }
    assert summary["daily_averages"] == {
        "calories": 558.0,
        "protein": 33.75,
        "carbs": 70.5,
        "fat": 12.15,
        "fiber": 9.0,
    }


@pytest.mark.asyncio
async def test_validate_plan_accumulates_floats_snacks_and_db_recipe_nutrition(async_session: AsyncSession, monkeypatch):
    """validate_plan should handle snacks, None values, decimal accumulation, and DB recipe lookup."""
    monkeypatch.setenv("USE_MOCK_AI", "True")
    recipe = Recipe(
        name="Salmon Salad",
        ingredients_json=json.dumps(["salmon", "greens"]),
        instructions_json=json.dumps(["Toss"]),
        nutrition_json=json.dumps({"calories": 420.6, "protein": 34.4, "carbs": 12.6, "fats": 24.6}),
    )
    async_session.add(recipe)
    await async_session.commit()
    await async_session.refresh(recipe)

    agent = NutritionAgent(session=async_session)
    estimate = AsyncMock(return_value={"calories": 200.6, "protein": 10.4, "carbs": 20.6, "fat": 5.6})
    monkeypatch.setattr(agent, "estimate_meal_nutrition", estimate)

    plan = {
        "days": [
            {
                "breakfast": {"name": "Smoothie", "ingredients": ["milk", "berries"], "nutrition": None},
                "lunch": {"recipe_id": recipe.id, "name": "Salmon Salad"},
                "snacks": [
                    {"name": "Almonds", "nutrition": {"calories": 160.2, "protein": 6.2, "carbs": 6.2, "fats": 14.2}}
                ],
            }
        ]
    }

    validated = await agent.validate_plan(plan)

    # Only Smoothie needed estimation because Salmon Salad resolved from DB and Almonds had inline nutrition
    estimate.assert_awaited_once_with("Smoothie", ["milk", "berries"])
    assert validated["days"][0]["daily_summary"] == {
        "calories": 781,
        "protein": 51,
        "carbs": 39,
        "fat": 44,
    }
    assert validated["nutritional_summary"]["total_weekly_calories"] == 781
    assert validated["nutritional_summary"]["avg_daily_calories"] == 781


@pytest.mark.asyncio
async def test_persist_daily_nutrition_from_plan_async_and_fiber(async_session: AsyncSession):
    """persist_daily_nutrition_from_plan should persist fiber and support AsyncSession."""
    user = User(email="persist@example.com", hashed_password="pw", postal_code="H4T1V6", household_size=1)
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)

    plan = {
        "days": [
            {
                "date": "2026-11-12",
                "meals": [
                    {"name": "Oats", "nutrition": {"calories": 350, "protein": 12, "carbs": 55, "fats": 7, "fiber": 9}},
                    {"name": "Lentil Soup", "nutrition": {"calories": 450, "protein": 22, "carbs": 60, "fat": 8, "fiber": 12}},
                ],
            }
        ]
    }

    agent = NutritionAgent(session=async_session)
    await agent.persist_daily_nutrition_from_plan(user.id, plan)
    await async_session.commit()

    record = (
        await async_session.execute(
            select(DailyNutrition).where(DailyNutrition.user_id == user.id, DailyNutrition.date == date(2026, 11, 12))
        )
    ).scalars().first()
    assert record is not None
    assert record.calories == 800.0
    assert record.protein == 34.0
    assert record.carbs == 115.0
    assert record.fats == 15.0
    assert record.fiber == 21.0


def test_offline_nutrition_quantity_scaling():
    """resolve_offline_nutrition should scale when unit word is ingredient name and support mixed fractions."""
    agent = NutritionAgent()
    one_chicken = agent.resolve_offline_nutrition(["1 chicken breast"])
    two_chicken = agent.resolve_offline_nutrition(["2 chicken breasts"])
    mixed_rice = agent.resolve_offline_nutrition(["1 1/2 cups rice"])
    half_rice = agent.resolve_offline_nutrition(["1/2 cup rice"])

    assert two_chicken["calories"] > one_chicken["calories"]
    assert mixed_rice["calories"] > half_rice["calories"]
