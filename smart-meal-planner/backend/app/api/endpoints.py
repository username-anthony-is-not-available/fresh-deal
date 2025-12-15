from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_async_session, get_session
from sqlmodel import Session
from app.models.all_models import User, MealPlan, Deal, Product, Store, RecipeRating, UserFavorite, Recipe, RecipeFeedback, RecipeIngredient
from app.agents.flipp_scraper import CANADIAN_STORES
# from app.agents.mock_scraper import MockScraperAgent
from app.services.shopping_optimizer import ShoppingListOptimizer
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from celery.result import AsyncResult
import json
from datetime import datetime, timedelta, timezone
from app.tasks import generate_meal_plan_task, scrape_task
from app.services.user_service import UserService
from app.schemas import UserUpdate, UserRead, RecipeRead, NutritionSummaryRead, RecipeFeedbackCreate

router = APIRouter()

class UserCreate(BaseModel):
    email: str
    password: str
    postal_code: str
    household_size: int
    dietary_preferences: str

class RecipeRatingCreate(BaseModel):
    rating: int

@router.get("/recipes", response_model=List[RecipeRead])
async def list_recipes(
    search: Optional[str] = None,
    cuisine: Optional[str] = None,
    prep_time: Optional[int] = None,
    session: AsyncSession = Depends(get_async_session)
):
    """List all recipes with optional search and filters."""
    statement = select(Recipe).distinct()
    if search:
        statement = statement.join(RecipeIngredient).where(
            func.lower(Recipe.name).contains(func.lower(search)) |
            func.lower(RecipeIngredient.name).contains(func.lower(search))
        )
    if cuisine:
        statement = statement.where(func.lower(Recipe.cuisine) == func.lower(cuisine))
    if prep_time:
        statement = statement.where(Recipe.prep_time_minutes <= prep_time)
    result = await session.execute(statement)
    recipes = result.scalars().all()
    return recipes


from app.services.substitution_service import substitution_service

@router.get("/recipes/{recipe_id}", response_model=RecipeRead)
async def get_recipe(recipe_id: int, session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(select(Recipe).where(Recipe.id == recipe_id))
    recipe = result.scalars().one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    # Manually load ingredients
    ingredients_result = await session.execute(
        select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe_id)
    )
    ingredients = ingredients_result.scalars().all()
    ingredient_names = [ing.name for ing in ingredients]

    substitutions = substitution_service.get_substitutions(ingredient_names)

    recipe_data = recipe.dict()
    recipe_data["ingredients"] = ingredient_names
    recipe_data["substitutions"] = substitutions

    return RecipeRead(**recipe_data)

@router.post("/recipes/{recipe_id}/rate")
async def rate_recipe(recipe_id: int, rating_in: RecipeRatingCreate, user_id: int = 1, session: AsyncSession = Depends(get_async_session)):
    # Hardcoded user_id=1 for MVP
    # Check if a rating already exists
    statement = select(RecipeRating).where(RecipeRating.user_id == user_id, RecipeRating.recipe_id == recipe_id)
    result = await session.execute(statement)
    existing_rating = result.scalars().first()

    if existing_rating:
        existing_rating.rating = rating_in.rating
        session.add(existing_rating)
    else:
        rating = RecipeRating(user_id=user_id, recipe_id=recipe_id, rating=rating_in.rating)
        session.add(rating)

    await session.commit()
    return {"message": "Rating submitted successfully"}


@router.post("/recipes/{recipe_id}/feedback")
async def submit_recipe_feedback(recipe_id: int, feedback_in: RecipeFeedbackCreate, user_id: int = 1, session: AsyncSession = Depends(get_async_session)):
    # Hardcoded user_id=1 for MVP
    feedback = RecipeFeedback(
        user_id=user_id,
        recipe_id=recipe_id,
        status=feedback_in.status,
        notes=feedback_in.notes
    )
    session.add(feedback)
    await session.commit()
    return {"message": "Feedback submitted successfully"}


@router.get("/recipes/{recipe_id}/average-rating")
async def get_average_rating(recipe_id: int, session: AsyncSession = Depends(get_async_session)):
    statement = select(func.avg(RecipeRating.rating)).where(RecipeRating.recipe_id == recipe_id)
    result = await session.execute(statement)
    average_rating = result.scalar_one_or_none()
    return {"average_rating": average_rating or 0}

@router.post("/recipes/{recipe_id}/favorite")
async def favorite_recipe(recipe_id: int, user_id: int = 1, session: AsyncSession = Depends(get_async_session)):
    # Hardcoded user_id=1 for MVP
    favorite = UserFavorite(user_id=user_id, recipe_id=recipe_id)
    session.add(favorite)
    await session.commit()
    return {"message": "Recipe favorited successfully"}

@router.delete("/recipes/{recipe_id}/favorite")
async def unfavorite_recipe(recipe_id: int, user_id: int = 1, session: AsyncSession = Depends(get_async_session)):
    # Hardcoded user_id=1 for MVP
    statement = select(UserFavorite).where(UserFavorite.user_id == user_id, UserFavorite.recipe_id == recipe_id)
    result = await session.execute(statement)
    favorite = result.scalars().first()

    if favorite:
        await session.delete(favorite)
        await session.commit()
        return {"message": "Recipe unfavorited successfully"}
    else:
        raise HTTPException(status_code=404, detail="Favorite not found")

@router.get("/users/me/favorites")
async def get_user_favorites(user_id: int = 1, session: AsyncSession = Depends(get_async_session)):
    # Hardcoded user_id=1 for MVP
    statement = select(Recipe).join(UserFavorite).where(UserFavorite.user_id == user_id)
    result = await session.execute(statement)
    favorites = result.scalars().all()
    return favorites

@router.post("/onboard")
async def onboard_user(user_in: UserCreate, session: AsyncSession = Depends(get_async_session)):
    user = User(
        email=user_in.email,
        hashed_password=user_in.password, # In a real app, you'd hash this
        postal_code=user_in.postal_code,
        household_size=user_in.household_size,
        dietary_preferences=user_in.dietary_preferences
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

@router.get("/users/{user_id}", response_model=UserRead)
async def get_user(user_id: int, session: AsyncSession = Depends(get_async_session)):
    user_service = UserService(session)
    user = await user_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(user_id: int, user_in: UserUpdate, session: AsyncSession = Depends(get_async_session)):
    user_service = UserService(session)
    user = await user_service.update_user(user_id, user_in)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.get("/users/{user_id}/nutrition-summary", response_model=NutritionSummaryRead)
async def get_nutrition_summary(user_id: int, session: AsyncSession = Depends(get_async_session)):
    user_service = UserService(session)
    summary = await user_service.get_meal_plan_nutrition_summary(user_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Nutrition summary not found")
    return summary

@router.post("/data/seed")
def seed_data(session: Session = Depends(get_session)):
    # Keep synchronous as it's a dev tool and uses MockScraperAgent which might be sync
    # scraper = MockScraperAgent(session)
    # count = scraper.generate_deals()
    return {"message": f"Seeded database with {0} deals."}

class ScrapeRequest(BaseModel):
    """Request body for scraping."""
    stores: List[str]
    postal_code: str = "H4T1V6"
    limit_per_store: int = 50

@router.post("/admin/scrape")
async def trigger_scrape(request: ScrapeRequest):
    """
    Triggers the background task to scrape grocery deals from the specified stores.
    
    This endpoint uses the ScraperAgent to orchestrate the scraping process,
    which may include direct browser scraping with a fallback to the Flipp API.
    """
    task = scrape_task.delay(
        stores=request.stores,
        postal_code=request.postal_code,
        limit_per_store=request.limit_per_store
    )
    return {
        "task_id": task.id, 
        "status": "Processing", 
        "stores": request.stores,
        "postal_code": request.postal_code
    }

@router.get("/admin/scrapers")
async def list_scrapers():
    """
    List available scrapers and their configurations.
    """
    available_stores = ["metro", "walmart", "maxi", "provigo", "iga"]
    return {
        "scrapers": [
            {
                "id": "default",
                "name": "Default Scraper",
                "description": "Uses a combination of direct scraping and the Flipp API.",
                "endpoint": "/admin/scrape",
                "method": "POST",
                "recommended": True,
                "stores": {store: store.capitalize() for store in available_stores}
            }
        ]
    }

@router.get("/admin/status/scrapers")
async def get_scraper_status(session: AsyncSession = Depends(get_async_session)):
    """
    Returns the last scraped timestamp for each store.
    """
    result = await session.execute(select(Store))
    stores = result.scalars().all()

    return [
        {
            "id": store.id,
            "name": store.name,
            "chain": store.chain,
            "last_scraped_at": store.last_scraped_at,
            "is_stale": store.is_stale,
        }
        for store in stores
    ]

@router.get("/deals")
async def list_deals(
    sort_by: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session)
):
    """List all active deals with product and store info."""
    statement = (
        select(Deal, Product, Store)
        .join(Product)
        .join(Store)
    )

    if sort_by == "category":
        statement = statement.order_by(Product.category)

    result = await session.execute(statement)
    results = result.all()

    deals_data = []
    for deal, product, store in results:
        deals_data.append({
            "id": deal.id,
            "product": product,
            "store": store,
            "price": deal.price,
            "original_price": deal.original_price,
            "discount_pct": deal.discount_pct,
            "valid_until": deal.valid_until,
            "is_stale": store.is_stale,
        })
    return deals_data

@router.post("/plans/generate")
async def generate_meal_plan(user_id: int):
    """
    Triggers meal plan generation in the background.
    Returns a task_id to poll.
    """
    task = generate_meal_plan_task.delay(user_id)
    return {"task_id": task.id, "status": "Processing"}

@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    Checks the status of a background task.
    """
    task_result = AsyncResult(task_id)
    if task_result.state == 'PENDING':
        return {"task_id": task_id, "status": "Pending"}
    elif task_result.state == 'REVOKED':
        return {"task_id": task_id, "status": "Stopped"}
    elif task_result.state != 'FAILURE':
        return {
            "task_id": task_id,
            "status": task_result.state,
            "result": task_result.result
        }
    else:
        # something went wrong in the background job
        return {
            "task_id": task_id,
            "status": "Failed",
            "error": str(task_result.info)
        }

@router.post("/tasks/{task_id}/stop")
async def stop_task(task_id: str):
    """
    Revokes/stops a running background task.
    """
    from app.celery_app import celery_app
    celery_app.control.revoke(task_id, terminate=True, signal='SIGTERM')
    return {"task_id": task_id, "status": "Stopped", "message": "Task revocation requested"}

@router.get("/plans/{user_id}/latest")
async def get_latest_plan(user_id: int, session: AsyncSession = Depends(get_async_session)):
    statement = select(MealPlan).where(MealPlan.user_id == user_id).order_by(MealPlan.created_at.desc())
    result = await session.execute(statement) # Changed exec to execute
    plan = result.scalars().first() # scalars() needed for getting the objects directly if select(MealPlan)
    if not plan:
        raise HTTPException(status_code=404, detail="No plan found")
    return json.loads(plan.content_json)

@router.get("/shopping/optimize")
async def optimize_shopping_list(
    user_id: int,
    strategy: str = "min_cost",
    session: AsyncSession = Depends(get_async_session)
):
    """
    Returns the optimized shopping list for the user's latest meal plan.
    """
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get latest plan
    statement = select(MealPlan).where(MealPlan.user_id == user_id).order_by(MealPlan.created_at.desc())
    result = await session.execute(statement)
    plan = result.scalars().first()

    if not plan:
        raise HTTPException(status_code=404, detail="No meal plan found. Generate one first.")

    plan_data = json.loads(plan.content_json)

    optimizer = ShoppingListOptimizer(session) # Passing async session
    result = await optimizer.generate_shopping_list_async(user, plan_data, strategy)

    return result
