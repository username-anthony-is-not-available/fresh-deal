import pytest
from httpx import AsyncClient, ASGITransport
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel.pool import StaticPool
from app.main import app
from app.core.db import get_async_session
from app.models.all_models import User, Recipe, RecipeFeedback
from app.api.auth_endpoints import get_current_user
from app.core.security import create_access_token
from sqlmodel import select
import pytest_asyncio

# Use aiosqlite for async testing
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
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    response = await client.post(
        "/auth/register",
        json={
            "email": "test@example.com",
            "password": "password",
            "postal_code": "H4T 1V6",
            "household_size": 2,
            "dietary_preferences": [],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
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
        json={
            "email": "test@test.com",
            "password": "password",
            "postal_code": "H1A 1A1",
            "household_size": 1,
            "dietary_preferences": ["vegetarian"],
        },
    )
    user_id = onboard_response.json()["id"]
    token = create_access_token(subject=user_id)
    headers = {"Authorization": f"Bearer {token}"}

    # Now, test the get endpoint with token
    response = await client.get(f"/api/users/{user_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
    assert data["postal_code"] == "H1A 1A1"
    assert data["household_size"] == 1
    assert data["dietary_preferences"] == ["vegetarian"]


@pytest.mark.asyncio
async def test_get_user_unauthorized_401(client: AsyncClient):
    response = await client.get("/api/users/1")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_user_forbidden_403(client: AsyncClient):
    onboard_response = await client.post(
        "/api/onboard",
        json={
            "email": "user1@test.com",
            "password": "password",
            "postal_code": "H1A 1A1",
            "household_size": 1,
            "dietary_preferences": [],
        },
    )
    user1_id = onboard_response.json()["id"]
    token1 = create_access_token(subject=user1_id)
    headers = {"Authorization": f"Bearer {token1}"}

    # User 1 tries to access User 2's data
    response = await client.get("/api/users/999", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_plans_generate_unauthorized_401(client: AsyncClient):
    response = await client.post("/api/plans/generate?user_id=1")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_pantry_forbidden_403(client: AsyncClient):
    onboard_response = await client.post(
        "/api/onboard",
        json={
            "email": "pantryuser@test.com",
            "password": "password",
            "postal_code": "H1A 1A1",
            "household_size": 1,
            "dietary_preferences": [],
        },
    )
    user_id = onboard_response.json()["id"]
    token = create_access_token(subject=user_id)
    headers = {"Authorization": f"Bearer {token}"}

    # Try to access another user's pantry
    response = await client.get("/api/pantry/999", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_user(client: AsyncClient):
    # First, create a user to update
    onboard_response = await client.post(
        "/api/onboard",
        json={
            "email": "test@test.com",
            "password": "password",
            "postal_code": "H2B 2B2",
            "household_size": 3,
            "dietary_preferences": [],
        },
    )
    user_id = onboard_response.json()["id"]
    token = create_access_token(subject=user_id)
    headers = {"Authorization": f"Bearer {token}"}

    # Now, test the patch endpoint
    update_data = {"postal_code": "J7Y 5K2", "household_size": 4}
    response = await client.patch(f"/api/users/{user_id}", json=update_data, headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
    assert data["postal_code"] == "J7Y 5K2"
    assert data["household_size"] == 4
    assert data["dietary_preferences"] == []  # Should not be changed

    # Verify the changes by fetching the user again
    get_response = await client.get(f"/api/users/{user_id}", headers=headers)
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert get_data["postal_code"] == "J7Y 5K2"
    assert get_data["household_size"] == 4


@pytest.mark.asyncio
async def test_submit_recipe_feedback(client: AsyncClient, session: AsyncSession):
    # 1. Create a user and a recipe
    user = User(
        email="feedback@test.com",
        hashed_password="password",
        postal_code="A1A 1A1",
        household_size=1,
    )
    recipe = Recipe(name="Test Soup", ingredients_json="[]", instructions_json="[]")
    session.add(user)
    session.add(recipe)
    await session.commit()
    await session.refresh(user)
    await session.refresh(recipe)

    # Endpoint is protected; override auth for this test.
    app.dependency_overrides[get_current_user] = lambda: user

    # 2. Submit feedback
    feedback_data = {"status": "made_it", "notes": "It was delicious!"}
    response = await client.post(
        f"/api/recipes/{recipe.id}/feedback", json=feedback_data
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Feedback submitted successfully"}

    # 3. Verify the feedback was saved in the database
    statement = select(RecipeFeedback).where(
        RecipeFeedback.recipe_id == recipe.id, RecipeFeedback.user_id == user.id
    )
    result = await session.execute(statement)
    feedback_entry = result.scalars().first()

    assert feedback_entry is not None
    assert feedback_entry.status == "made_it"
    assert feedback_entry.notes == "It was delicious!"

    app.dependency_overrides.pop(get_current_user, None)
