
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlmodel import Session, SQLModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.models.all_models import User, Recipe, UserFavorite
from app.core.security import create_access_token

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
async def test_rate_recipe_authenticated(client: AsyncClient, test_user: User, test_recipe: Recipe):
    access_token = create_access_token(subject=test_user.id)
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await client.post(
        f"/api/recipes/{test_recipe.id}/rate",
        json={"rating": 5},
        headers=headers
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Rating submitted successfully"}

    response = await client.get(
        f"/api/recipes/{test_recipe.id}/my-rating",
        headers=headers
    )
    assert response.status_code == 200
    assert response.json() == {"rating": 5}

@pytest.mark.asyncio
async def test_get_average_rating(client: AsyncClient, test_user: User, test_recipe: Recipe):
    access_token = create_access_token(subject=test_user.id)
    headers = {"Authorization": f"Bearer {access_token}"}
    await client.post(
        f"/api/recipes/{test_recipe.id}/rate",
        json={"rating": 5},
        headers=headers
    )

    response = await client.get(f"/api/recipes/{test_recipe.id}/average-rating")
    assert response.status_code == 200
    assert response.json() == {"average_rating": 5}

@pytest.mark.asyncio
async def test_favorite_recipe(client: AsyncClient, test_user: User, test_recipe: Recipe):
    access_token = create_access_token(subject=test_user.id)
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await client.post(f"/api/recipes/{test_recipe.id}/favorite", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"message": "Recipe favorited successfully"}

@pytest.mark.asyncio
async def test_unfavorite_recipe(client: AsyncClient, test_user: User, test_recipe: Recipe, session: AsyncSession):
    access_token = create_access_token(subject=test_user.id)
    headers = {"Authorization": f"Bearer {access_token}"}

    # Favorite the recipe first
    favorite = UserFavorite(user_id=test_user.id, recipe_id=test_recipe.id)
    session.add(favorite)
    await session.commit()

    response = await client.delete(f"/api/recipes/{test_recipe.id}/favorite", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"message": "Recipe unfavorited successfully"}

@pytest.mark.asyncio
async def test_get_user_favorites(client: AsyncClient, test_user: User, test_recipe: Recipe, session: AsyncSession):
    access_token = create_access_token(subject=test_user.id)
    headers = {"Authorization": f"Bearer {access_token}"}

    # Favorite the recipe first
    favorite = UserFavorite(user_id=test_user.id, recipe_id=test_recipe.id)
    session.add(favorite)
    await session.commit()

    response = await client.get("/api/users/me/favorites", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Recipe"
