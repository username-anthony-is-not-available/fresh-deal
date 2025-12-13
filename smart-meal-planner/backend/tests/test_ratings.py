
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlmodel import Session, SQLModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.models.all_models import User, Recipe

# Re-using the test setup from test_api.py
from .test_api import session_fixture, client_fixture

@pytest_asyncio.fixture(name="test_user")
async def user_fixture(session: AsyncSession):
    user = User(
        email="test@example.com",
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
        name="Test Recipe",
        ingredients_json='[{"item": "ingredient1"}]',
        instructions_json='["step 1"]'
    )
    session.add(recipe)
    await session.commit()
    await session.refresh(recipe)
    return recipe

@pytest.mark.asyncio
async def test_rate_recipe(client: AsyncClient, test_user: User, test_recipe: Recipe):
    response = await client.post(
        f"/api/recipes/{test_recipe.id}/rate?user_id={test_user.id}",
        json={"rating": 5}
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Rating submitted successfully"}

@pytest.mark.asyncio
async def test_get_average_rating(client: AsyncClient, test_user: User, test_recipe: Recipe):
    await client.post(
        f"/api/recipes/{test_recipe.id}/rate?user_id={test_user.id}",
        json={"rating": 5}
    )

    response = await client.get(f"/api/recipes/{test_recipe.id}/average-rating")
    assert response.status_code == 200
    assert response.json() == {"average_rating": 5}

@pytest.mark.asyncio
async def test_favorite_recipe(client: AsyncClient, test_user: User, test_recipe: Recipe):
    response = await client.post(f"/api/recipes/{test_recipe.id}/favorite?user_id={test_user.id}")
    assert response.status_code == 200
    assert response.json() == {"message": "Recipe favorited successfully"}

@pytest.mark.asyncio
async def test_unfavorite_recipe(client: AsyncClient, test_user: User, test_recipe: Recipe):
    await client.post(f"/api/recipes/{test_recipe.id}/favorite?user_id={test_user.id}")
    response = await client.delete(f"/api/recipes/{test_recipe.id}/favorite?user_id={test_user.id}")
    assert response.status_code == 200
    assert response.json() == {"message": "Recipe unfavorited successfully"}

@pytest.mark.asyncio
async def test_get_user_favorites(client: AsyncClient, test_user: User, test_recipe: Recipe):
    await client.post(f"/api/recipes/{test_recipe.id}/favorite?user_id={test_user.id}")

    response = await client.get(f"/api/users/me/favorites?user_id={test_user.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Recipe"
