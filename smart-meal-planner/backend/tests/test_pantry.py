import json
from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.pool import StaticPool

from app.main import app
from app.core.db import get_async_session
from app.models.all_models import MealPlan, PantryItem, User
from app.core.security import create_access_token
from sqlmodel import select


DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@pytest_asyncio.fixture(name="session", scope="function")
async def session_fixture():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest_asyncio.fixture(name="client", scope="function")
async def client_fixture(session: AsyncSession):
    def get_session_override():
        return session

    app.dependency_overrides[get_async_session] = get_session_override

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_pantry_add_and_consume_latest_plan(
    client: AsyncClient, session: AsyncSession
):
    # Create a user
    user = User(
        email="pantry@test.com",
        hashed_password="x",
        postal_code="H1A 1A1",
        household_size=4,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_access_token(subject=user.id)
    headers = {"Authorization": f"Bearer {token}"}

    # Add pantry items (starts empty)
    add_resp = await client.post(
        f"/api/pantry/{user.id}/add",
        json={
            "items": [
                {"name": "Chicken Breast (Boneless)", "quantity": 1.0, "unit": "kg"},
                {"name": "Broccoli Crowns", "quantity": 2, "unit": "each"},
            ]
        },
        headers=headers,
    )
    assert add_resp.status_code == 200

    # Create a plan that uses 0.5kg chicken + 1 broccoli (scale=1)
    plan_data = {
        "meal_plan": [
            {
                "day": 1,
                "date": "2026-01-01",
                "breakfast": {"ingredients": []},
                "lunch": {"ingredients": []},
                "dinner": {
                    "ingredients": [
                        {
                            "item": "Chicken Breast (Boneless)",
                            "quantity": 0.5,
                            "unit": "kg",
                        },
                        {"item": "Broccoli Crowns", "quantity": 1, "unit": "each"},
                    ]
                },
            }
        ]
    }
    meal_plan = MealPlan(
        user_id=user.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 7),
        content_json=json.dumps(plan_data),
    )
    session.add(meal_plan)
    await session.commit()

    consume_resp = await client.post(f"/api/pantry/{user.id}/consume-latest-plan", headers=headers)
    assert consume_resp.status_code == 200
    payload = consume_resp.json()
    assert payload["consumed_count"] == 2

    # Verify pantry decreased
    items_resp = await client.get(f"/api/pantry/{user.id}", headers=headers)
    assert items_resp.status_code == 200
    items = {(i["name"], i["unit"]): i["quantity"] for i in items_resp.json()}

    assert items[("Chicken Breast (Boneless)", "kg")] == 0.5
    assert items[("Broccoli Crowns", "each")] == 1.0


@pytest.mark.asyncio
async def test_pantry_item_deletes_when_depleted(
    client: AsyncClient, session: AsyncSession
):
    user = User(
        email="pantry2@test.com",
        hashed_password="x",
        postal_code="H1A 1A1",
        household_size=4,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_access_token(subject=user.id)
    headers = {"Authorization": f"Bearer {token}"}

    # Add exactly what will be consumed
    await client.post(
        f"/api/pantry/{user.id}/add",
        json={"items": [{"name": "Rice (Basmati 2kg)", "quantity": 0.2, "unit": "kg"}]},
        headers=headers,
    )

    plan_data = {
        "meal_plan": [
            {
                "day": 1,
                "date": "2026-01-01",
                "dinner": {
                    "ingredients": [
                        {"item": "Rice (Basmati 2kg)", "quantity": 0.2, "unit": "kg"}
                    ]
                },
            }
        ]
    }
    meal_plan = MealPlan(
        user_id=user.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 7),
        content_json=json.dumps(plan_data),
    )
    session.add(meal_plan)
    await session.commit()

    await client.post(f"/api/pantry/{user.id}/consume-latest-plan", headers=headers)

    # Should be gone
    items_resp = await client.get(f"/api/pantry/{user.id}", headers=headers)
    assert items_resp.status_code == 200
    assert items_resp.json() == []

    # Double-check DB
    result = await session.execute(
        select(PantryItem).where(PantryItem.user_id == user.id)
    )
    assert result.scalars().first() is None
