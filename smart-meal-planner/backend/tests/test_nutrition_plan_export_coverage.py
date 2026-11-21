"""Coverage tests for app/api/nutrition.py and app/api/plan_export.py."""
import json
from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import StaticPool
from sqlmodel import Session as SyncSession, SQLModel, create_engine, select

from app.core.db import get_session
from app.core.security import create_access_token
from app.main import app
from app.models.all_models import DailyNutrition, MealPlan, User


@pytest_asyncio.fixture(name="sync_env")
async def sync_env_fixture(client: AsyncClient):
    """A sync in-memory DB + get_session override for the sync endpoints."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    sync_session = SyncSession(engine)
    user = User(
        email="nutri@test.com",
        hashed_password="hashed",
        postal_code="H4T1V6",
        household_size=2,
        dietary_preferences_json=json.dumps(["vegan"]),
        allergies_json=json.dumps(["peanuts"]),
    )
    sync_session.add(user)
    sync_session.commit()
    sync_session.refresh(user)

    def _override():
        yield sync_session

    app.dependency_overrides[get_session] = _override
    try:
        yield client, sync_session, user
    finally:
        app.dependency_overrides.pop(get_session, None)
        sync_session.close()


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def _plan(user_id):
    return MealPlan(
        user_id=user_id,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=6),
        content_json=json.dumps(
            {
                "weekly_overview": "Eat well.",
                "days": [
                    {
                        "date": date.today().isoformat(),
                        "meals": [
                            {
                                "recipe_name": "Soup",
                                "type": "Lunch",
                                "reason": "tasty",
                                "ingredients": [{"item": "Chicken", "amount": "1 kg"}],
                            },
                            {"recipe_name": "Salad", "type": "Dinner"},
                        ],
                    },
                    {"date": (date.today() + timedelta(days=1)).isoformat(), "meals": []},
                ],
            }
        ),
    )


# ---------------------------------------------------------------------------
# nutrition.py
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nutrition_goal_create_update_get(sync_env):
    client, sync_session, user = sync_env
    headers = _headers(user)

    # No goal yet -> 404.
    resp = await client.get("/api/users/me/nutrition-goal", headers=headers)
    assert resp.status_code == 404

    # Create.
    resp = await client.post(
        "/api/users/me/nutrition-goal",
        json={"goal_type": "maintenance", "target_calories": 2000, "target_protein": 150},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["target_calories"] == 2000

    # Update the existing goal.
    resp = await client.post(
        "/api/users/me/nutrition-goal",
        json={"target_calories": 1800},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["target_calories"] == 1800

    resp = await client.get("/api/users/me/nutrition-goal", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["target_calories"] == 1800


@pytest.mark.asyncio
async def test_nutrition_summary(sync_env):
    client, sync_session, user = sync_env
    headers = _headers(user)
    sync_session.add(
        DailyNutrition(
            user_id=user.id, date=date.today(), calories=1800,
            protein=120, carbs=200, fats=60, fiber=25,
        )
    )
    sync_session.commit()
    resp = await client.get(
        "/api/users/me/nutrition-summary",
        params={
            "start_date": date.today().isoformat(),
            "end_date": date.today().isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_dietary_profiles(client: AsyncClient):
    resp = await client.get("/api/nutrition/dietary-profiles")
    assert resp.status_code == 200
    assert len(resp.json()) > 0


@pytest.mark.asyncio
async def test_recommended_nutrition_goal(sync_env):
    client, sync_session, user = sync_env
    headers = _headers(user)
    # Explicit restrictions, no persistence.
    resp = await client.post(
        "/api/users/me/nutrition-goal/recommended",
        json={"goal_type": "weight_loss", "dietary_restrictions": ["vegan"]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["goal_type"] == "weight_loss"
    # Apply to goal: creates it (user has no goal yet).
    resp = await client.post(
        "/api/users/me/nutrition-goal/recommended",
        json={"goal_type": "maintenance", "apply_to_goal": True},
        headers=headers,
    )
    assert resp.status_code == 200
    # Apply again: updates the existing goal.
    resp = await client.post(
        "/api/users/me/nutrition-goal/recommended",
        json={"goal_type": "muscle_gain", "apply_to_goal": True},
        headers=headers,
    )
    assert resp.status_code == 200
    resp = await client.get("/api/users/me/nutrition-goal", headers=headers)
    assert resp.json()["goal_type"] == "muscle_gain"


@pytest.mark.asyncio
async def test_nutrition_compliance(sync_env):
    client, sync_session, user = sync_env
    headers = _headers(user)
    # Empty state: no records, no goal, no plan.
    resp = await client.get("/api/users/me/nutrition-compliance", headers=headers)
    assert resp.status_code == 200
    # With a goal, a plan and daily records.
    sync_session.add(_plan(user.id))
    sync_session.add(
        DailyNutrition(
            user_id=user.id, date=date.today(), calories=1900,
            protein=140, carbs=210, fats=65, fiber=28,
        )
    )
    sync_session.commit()
    resp = await client.get(
        "/api/users/me/nutrition-compliance", params={"days": 7}, headers=headers
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# plan_export.py
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(name="async_user")
async def async_user_fixture(session: AsyncSession):
    user = User(
        email="plan@test.com",
        hashed_password="hashed",
        postal_code="H4T1V6",
        household_size=2,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_export_plan_ical(client: AsyncClient, session: AsyncSession, async_user):
    # plan_export authenticates + reads plans through the ASYNC session.
    user = async_user
    headers = _headers(user)
    # Wrong user -> 403.
    resp = await client.get(f"/api/plans/{user.id + 1}/export/ical", headers=headers)
    assert resp.status_code == 403
    # No plan yet -> 404.
    resp = await client.get(f"/api/plans/{user.id}/export/ical", headers=headers)
    assert resp.status_code == 404
    # Happy path.
    session.add(_plan(user.id))
    await session.commit()
    resp = await client.get(f"/api/plans/{user.id}/export/ical", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/calendar")
    assert b"Soup" in resp.content
    # Empty content -> 404.
    plan = (await session.execute(select(MealPlan))).scalars().first()
    plan.content_json = ""
    session.add(plan)
    await session.commit()
    resp = await client.get(f"/api/plans/{user.id}/export/ical", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_plan_pdf(client: AsyncClient, session: AsyncSession, async_user):
    user = async_user
    headers = _headers(user)
    resp = await client.get(f"/api/plans/{user.id + 1}/export/pdf", headers=headers)
    assert resp.status_code == 403
    resp = await client.get(f"/api/plans/{user.id}/export/pdf", headers=headers)
    assert resp.status_code == 404
    session.add(_plan(user.id))
    await session.commit()
    resp = await client.get(f"/api/plans/{user.id}/export/pdf", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.content[:4] == b"%PDF"
