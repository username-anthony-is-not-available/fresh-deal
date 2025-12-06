
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

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

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
