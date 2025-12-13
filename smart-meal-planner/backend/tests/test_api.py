
import os
import pytest
import asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel.pool import StaticPool
from app.main import app
from app.core.db import get_async_session, get_session
import pytest_asyncio

# Use aiosqlite for async testing
DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

@pytest_asyncio.fixture(name="session")
async def session_fixture():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session

@pytest_asyncio.fixture(name="client")
async def client_fixture(session: AsyncSession):
    def get_session_override():
        return session

    app.dependency_overrides[get_async_session] = get_session_override

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Smart Meal Planner API is running"}

@pytest.mark.asyncio
async def test_onboard_user(client: AsyncClient):
    response = await client.post(
        "/api/onboard",
        json={"postal_code": "H4T 1V6", "household_size": 2, "dietary_preferences": "None"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["postal_code"] == "H4T 1V6"
    assert "id" in data

@pytest.mark.asyncio
async def test_deals_empty(client: AsyncClient):
    response = await client.get("/api/deals")
    assert response.status_code == 200
    assert response.json() == []

@pytest.mark.asyncio
async def test_get_user(client: AsyncClient):
    # First, create a user to fetch
    onboard_response = await client.post(
        "/api/onboard",
        json={"postal_code": "H1A 1A1", "household_size": 1, "dietary_preferences": "Vegetarian"}
    )
    user_id = onboard_response.json()["id"]

    # Now, test the get endpoint
    response = await client.get(f"/api/users/{user_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
    assert data["postal_code"] == "H1A 1A1"
    assert data["household_size"] == 1
    assert data["dietary_preferences"] == "Vegetarian"

@pytest.mark.asyncio
async def test_update_user(client: AsyncClient):
    # First, create a user to update
    onboard_response = await client.post(
        "/api/onboard",
        json={"postal_code": "H2B 2B2", "household_size": 3, "dietary_preferences": "None"}
    )
    user_id = onboard_response.json()["id"]

    # Now, test the patch endpoint
    update_data = {"postal_code": "J7Y 5K2", "household_size": 4}
    response = await client.patch(f"/api/users/{user_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
    assert data["postal_code"] == "J7Y 5K2"
    assert data["household_size"] == 4
    assert data["dietary_preferences"] == "None" # Should not be changed

    # Verify the changes by fetching the user again
    get_response = await client.get(f"/api/users/{user_id}")
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert get_data["postal_code"] == "J7Y 5K2"
    assert get_data["household_size"] == 4
