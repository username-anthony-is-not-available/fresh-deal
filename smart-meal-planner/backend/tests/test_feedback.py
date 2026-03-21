
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.all_models import User, Recipe, MealPlan, Feedback
from app.core.security import create_access_token

@pytest_asyncio.fixture(name="test_user")
async def user_fixture(session: AsyncSession):
    user = User(
        email="feedback_test@example.com",
        hashed_password="password",
        postal_code="H1A 1A1",
        household_size=2
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

@pytest_asyncio.fixture(name="test_recipe")
async def recipe_fixture(session: AsyncSession):
    recipe = Recipe(
        name="Feedback Test Recipe",
        ingredients_json='[{"item": "ingredient1"}]',
        instructions_json='["step 1"]'
    )
    session.add(recipe)
    await session.commit()
    await session.refresh(recipe)
    return recipe

@pytest_asyncio.fixture(name="test_meal_plan")
async def meal_plan_fixture(session: AsyncSession, test_user: User):
    from datetime import date
    meal_plan = MealPlan(
        user_id=test_user.id,
        start_date=date(2024, 7, 29),
        end_date=date(2024, 8, 4),
        content_json='{"meal_plan": []}'
    )
    session.add(meal_plan)
    await session.commit()
    await session.refresh(meal_plan)
    return meal_plan

@pytest.mark.asyncio
async def test_create_recipe_feedback(client: AsyncClient, test_user: User, test_recipe: Recipe):
    access_token = create_access_token(subject=test_user.id)
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await client.post(
        "/api/feedback",
        json={"recipe_id": test_recipe.id, "rating": 5, "comment": "Great recipe!"},
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["recipe_id"] == test_recipe.id
    assert data["rating"] == 5
    assert data["comment"] == "Great recipe!"

@pytest.mark.asyncio
async def test_create_meal_plan_feedback(client: AsyncClient, test_user: User, test_meal_plan: MealPlan):
    access_token = create_access_token(subject=test_user.id)
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await client.post(
        "/api/feedback",
        json={"meal_plan_id": test_meal_plan.id, "rating": 4, "comment": "Nice variety."},
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meal_plan_id"] == test_meal_plan.id
    assert data["rating"] == 4
    assert data["comment"] == "Nice variety."

@pytest.mark.asyncio
async def test_list_feedback(client: AsyncClient, test_user: User, test_recipe: Recipe, session: AsyncSession):
    access_token = create_access_token(subject=test_user.id)
    headers = {"Authorization": f"Bearer {access_token}"}

    feedback = Feedback(user_id=test_user.id, recipe_id=test_recipe.id, rating=5, comment="Test")
    session.add(feedback)
    await session.commit()

    response = await client.get("/api/feedback", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["comment"] == "Test"

@pytest.mark.asyncio
async def test_feedback_summary(client: AsyncClient, test_user: User, session: AsyncSession):
    access_token = create_access_token(subject=test_user.id)
    headers = {"Authorization": f"Bearer {access_token}"}

    f1 = Feedback(user_id=test_user.id, recipe_id=1, rating=5)
    f2 = Feedback(user_id=test_user.id, meal_plan_id=1, rating=3)
    session.add(f1)
    session.add(f2)
    await session.commit()

    response = await client.get("/api/feedback/summary", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["average_recipe_rating"] == 5.0
    assert data["average_meal_plan_rating"] == 3.0
    assert data["total_feedback_count"] >= 2
