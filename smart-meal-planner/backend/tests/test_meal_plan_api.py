import pytest
import json
from httpx import AsyncClient, ASGITransport
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel.pool import StaticPool
from app.main import app
from app.core.db import get_async_session
from app.models.all_models import User, MealPlan, Recipe, RecipeIngredient
from datetime import date, timedelta
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
async def test_get_latest_plan_has_ingredients(client: AsyncClient, session: AsyncSession):
    # 1. Setup data: User, Recipe, Ingredients, and a MealPlan
    user = User(
        email="plan_test@example.com",
        hashed_password="password",
        postal_code="H4T 1V6",
        household_size=2
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    recipe = Recipe(
        id=1,
        name="Chicken Stir-Fry",
        ingredients_json=json.dumps([{"item": "Chicken", "quantity": 1, "unit": "kg"}]),
        instructions_json="[]"
    )
    session.add(recipe)

    ingredient = RecipeIngredient(recipe_id=1, name="chicken")
    session.add(ingredient)
    await session.commit()

    # Create a meal plan content that looks like what LLMService + PlannerAgent would produce
    # PlannerAgent's _validate_and_enrich adds the 'ingredients' field.
    plan_content = {
        "meal_plan": [
            {
                "day": 1,
                "day_name": "Monday",
                "date": str(date.today()),
                "breakfast": {
                    "recipe_id": 1,
                    "recipe_name": "Chicken Stir-Fry",
                    "reason": "Uses deals",
                    "servings": 2,
                    "scaled_for_household": True,
                    "ingredients": [{"item": "Chicken", "quantity": 1, "unit": "kg"}]
                }
            }
        ]
    }

    meal_plan = MealPlan(
        user_id=user.id,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=6),
        content_json=json.dumps(plan_content)
    )
    session.add(meal_plan)
    await session.commit()

    # 2. Call the API
    response = await client.get(f"/api/plans/{user.id}/latest")

    assert response.status_code == 200
    data = response.json()

    # 3. Assert ingredients are present
    assert "meal_plan" in data
    first_day = data["meal_plan"][0]
    assert "breakfast" in first_day
    assert "ingredients" in first_day["breakfast"]
    assert first_day["breakfast"]["ingredients"][0]["item"] == "Chicken"
