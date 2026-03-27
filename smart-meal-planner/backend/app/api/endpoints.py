from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_async_session, get_session
from sqlmodel import Session
from app.api.auth_endpoints import get_current_user, get_current_user_optional
from app.models.all_models import (
    User,
    MealPlan,
    Deal,
    Product,
    Store,
    RecipeRating,
    UserFavorite,
    Recipe,
    RecipeFeedback,
    RecipeIngredient,
    Feedback,
)

from app.agents.mock_scraper import MockScraperAgent
from app.services.shopping_optimizer import ShoppingListOptimizer
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from celery.result import AsyncResult
import json
from app.tasks import generate_meal_plan_task, scrape_task
from app.services.user_service import UserService
from app.services.llm_service import LLMService
from app.schemas import (
    UserUpdate,
    UserRead,
    RecipeRead,
    NutritionSummaryRead,
    RecipeFeedbackCreate,
    RecipeRatingCreate,
    FeedbackCreate,
    FeedbackRead,
    PantryAddRequest,
    PantryItemRead,
)

from app.models.all_models import PantryItem
from app.services.pantry_service import PantryService
from app.services.substitution_service import substitution_service
from app.services.scraper_health_service import ScraperHealthService
from app.services.geospatial_service import GeospatialService

router = APIRouter()

# Approximate CAD value per point for major loyalty programs
LOYALTY_POINT_VALUES = {
    "PC Optimum": 0.001,  # $10 per 10,000 points
    "Scene+": 0.01,  # $10 per 1,000 points
    "Moi": 0.008,  # $1 per 125 points
    "AIR MILES": 0.105,  # Approx. $10 per 95 miles, can vary
}


class UserCreate(BaseModel):
    email: str
    password: str
    postal_code: str
    household_size: int
    dietary_preferences: List[str]
    allergies: List[str] = []


@router.get("/recipes", response_model=List[RecipeRead])
async def list_recipes(
    search: Optional[str] = None,
    cuisine: Optional[str] = None,
    prep_time: Optional[int] = None,
    session: AsyncSession = Depends(get_async_session),
):
    """List all recipes with optional search and filters."""
    statement = (
        select(
            Recipe,
            func.coalesce(func.avg(RecipeRating.rating), 0).label("average_rating"),
        )
        .outerjoin(RecipeRating, Recipe.id == RecipeRating.recipe_id)
        .group_by(Recipe.id)
        .distinct()
    )

    if search:
        statement = statement.join(RecipeIngredient).where(
            func.lower(Recipe.name).contains(func.lower(search))
            | func.lower(RecipeIngredient.name).contains(func.lower(search))
        )
    if cuisine:
        statement = statement.where(func.lower(Recipe.cuisine) == func.lower(cuisine))
    if prep_time:
        statement = statement.where(Recipe.prep_time_minutes <= prep_time)

    result = await session.execute(statement)
    recipes_with_ratings = result.all()

    response = []
    for recipe, average_rating in recipes_with_ratings:
        recipe_data = recipe.dict()
        recipe_data["average_rating"] = average_rating
        response.append(RecipeRead(**recipe_data))

    return response


@router.get("/recipes/{recipe_id}", response_model=RecipeRead)
async def get_recipe(
    recipe_id: int,
    servings: Optional[int] = None,
    session: AsyncSession = Depends(get_async_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    statement = (
        select(
            Recipe,
            func.coalesce(func.avg(RecipeRating.rating), 0).label("average_rating"),
        )
        .outerjoin(RecipeRating, Recipe.id == RecipeRating.recipe_id)
        .where(Recipe.id == recipe_id)
        .group_by(Recipe.id)
    )
    result = await session.execute(statement)
    result_tuple = result.one_or_none()

    if not result_tuple:
        raise HTTPException(status_code=404, detail="Recipe not found")

    recipe, average_rating = result_tuple

    # Determine target servings
    target_servings = servings
    if not target_servings and current_user:
        target_servings = current_user.household_size
    if not target_servings:
        target_servings = recipe.servings

    # Get structured ingredients
    try:
        structured_ingredients = json.loads(recipe.ingredients_json)
    except (json.JSONDecodeError, TypeError):
        structured_ingredients = []

    # Scale ingredients
    from app.services.recipe_service import RecipeService

    scaled_ingredients = RecipeService.scale_ingredients(
        structured_ingredients, recipe.servings, target_servings
    )

    # Get substitutions
    ingredient_names = [ing.get("item", ing.get("name", "")) for ing in structured_ingredients if isinstance(ing, dict)]
    if not ingredient_names:
        # Fallback to names only if not dicts
        ingredient_names = [str(ing) for ing in structured_ingredients]

    substitutions = substitution_service.get_substitutions(ingredient_names)

    recipe_data = recipe.dict()
    recipe_data["ingredients"] = scaled_ingredients
    recipe_data["substitutions"] = substitutions
    recipe_data["average_rating"] = average_rating
    recipe_data["servings"] = target_servings

    return RecipeRead(**recipe_data)


@router.get("/recipes/top-rated", response_model=List[RecipeRead])
async def get_top_rated_recipes(
    limit: int = 10, session: AsyncSession = Depends(get_async_session)
):
    """Returns the top-rated recipes."""
    statement = (
        select(
            Recipe,
            func.coalesce(func.avg(RecipeRating.rating), 0).label("average_rating"),
        )
        .outerjoin(RecipeRating, Recipe.id == RecipeRating.recipe_id)
        .group_by(Recipe.id)
        .order_by(func.coalesce(func.avg(RecipeRating.rating), 0).desc())
        .limit(limit)
    )
    result = await session.execute(statement)
    recipes_with_ratings = result.all()

    response = []
    for recipe, average_rating in recipes_with_ratings:
        recipe_data = recipe.dict()
        recipe_data["average_rating"] = average_rating
        response.append(RecipeRead(**recipe_data))

    return response


@router.post("/recipes/{recipe_id}/rate")
async def rate_recipe(
    recipe_id: int,
    rating_in: RecipeRatingCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    # Check if a rating already exists
    statement = select(RecipeRating).where(
        RecipeRating.user_id == current_user.id, RecipeRating.recipe_id == recipe_id
    )
    result = await session.execute(statement)
    existing_rating = result.scalars().first()

    if existing_rating:
        existing_rating.rating = rating_in.rating
        session.add(existing_rating)
    else:
        rating = RecipeRating(
            user_id=current_user.id, recipe_id=recipe_id, rating=rating_in.rating
        )
        session.add(rating)

    await session.commit()
    return {"message": "Rating submitted successfully"}


@router.post("/recipes/{recipe_id}/feedback")
async def submit_recipe_feedback(
    recipe_id: int,
    feedback_in: RecipeFeedbackCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    feedback = RecipeFeedback(
        user_id=current_user.id,
        recipe_id=recipe_id,
        status=feedback_in.status,
        notes=feedback_in.notes,
    )
    session.add(feedback)
    await session.commit()
    return {"message": "Feedback submitted successfully"}


@router.get("/recipes/{recipe_id}/average-rating")
async def get_average_rating(
    recipe_id: int, session: AsyncSession = Depends(get_async_session)
):
    statement = select(func.avg(RecipeRating.rating)).where(
        RecipeRating.recipe_id == recipe_id
    )
    result = await session.execute(statement)
    average_rating = result.scalar_one_or_none()
    return {"average_rating": average_rating or 0}


@router.get("/recipes/{recipe_id}/my-rating")
async def get_my_rating(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    statement = select(RecipeRating).where(
        RecipeRating.recipe_id == recipe_id, RecipeRating.user_id == current_user.id
    )
    result = await session.execute(statement)
    rating = result.scalar_one_or_none()
    return {"rating": rating.rating if rating else None}


@router.post("/recipes/{recipe_id}/favorite")
async def favorite_recipe(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    favorite = UserFavorite(user_id=current_user.id, recipe_id=recipe_id)
    session.add(favorite)
    await session.commit()
    return {"message": "Recipe favorited successfully"}


@router.delete("/recipes/{recipe_id}/favorite")
async def unfavorite_recipe(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    statement = select(UserFavorite).where(
        UserFavorite.user_id == current_user.id, UserFavorite.recipe_id == recipe_id
    )
    result = await session.execute(statement)
    favorite = result.scalars().first()

    if favorite:
        await session.delete(favorite)
        await session.commit()
        return {"message": "Recipe unfavorited successfully"}
    else:
        raise HTTPException(status_code=404, detail="Favorite not found")


@router.get("/users/me/favorites")
async def get_user_favorites(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    statement = (
        select(Recipe).join(UserFavorite).where(UserFavorite.user_id == current_user.id)
    )
    result = await session.execute(statement)
    favorites = result.scalars().all()
    return favorites


@router.post("/onboard")
async def onboard_user(
    user_in: UserCreate, session: AsyncSession = Depends(get_async_session)
):
    user = User(
        email=user_in.email,
        hashed_password=user_in.password,  # In a real app, you'd hash this
        postal_code=user_in.postal_code,
        household_size=user_in.household_size,
        dietary_preferences_json=json.dumps(user_in.dietary_preferences),
        allergies_json=json.dumps(user_in.allergies),
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
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    session: AsyncSession = Depends(get_async_session),
):
    user_service = UserService(session)
    user = await user_service.update_user(user_id, user_in)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/users/{user_id}/nutrition-summary", response_model=NutritionSummaryRead)
async def get_nutrition_summary(
    user_id: int, session: AsyncSession = Depends(get_async_session)
):
    user_service = UserService(session)
    summary = await user_service.get_meal_plan_nutrition_summary(user_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Nutrition summary not found")
    return summary


@router.post("/data/seed")
def seed_data(session: Session = Depends(get_session)):
    # Keep synchronous as it's a dev tool and uses MockScraperAgent which might be sync
    scraper = MockScraperAgent(session)
    count = scraper.generate_deals()
    return {"message": f"Seeded database with {count} deals."}


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
        limit_per_store=request.limit_per_store,
    )
    return {
        "task_id": task.id,
        "status": "Processing",
        "stores": request.stores,
        "postal_code": request.postal_code,
    }


@router.post("/admin/scrape/flipp")
async def trigger_flipp_scrape(request: ScrapeRequest):
    """
    Dedicated endpoint for Flipp API scraping, as expected by the frontend.
    """
    return await trigger_scrape(request)


@router.post("/admin/scrape/{store_name}")
async def trigger_specific_scrape(
    store_name: str,
    postal_code: str = "H4T1V6",
    limit: int = 50
):
    """
    Triggers a scrape for a specific store. Matches 'Legacy' buttons in the frontend.
    """
    task = scrape_task.delay(
        stores=[store_name],
        postal_code=postal_code,
        limit_per_store=limit,
    )
    return {
        "task_id": task.id,
        "status": "Processing",
        "stores": [store_name],
        "postal_code": postal_code,
    }


@router.get("/admin/scrapers")
async def list_scrapers():
    """
    List available scrapers and their configurations.
    """
    available_stores = ["metro", "walmart", "maxi", "provigo", "iga", "super_c"]
    return {
        "scrapers": [
            {
                "id": "default",
                "name": "Default Scraper",
                "description": "Uses a combination of direct scraping and the Flipp API.",
                "endpoint": "/admin/scrape",
                "method": "POST",
                "recommended": True,
                "stores": {store: store.capitalize() for store in available_stores},
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


@router.get("/admin/scrapers/health")
async def get_scrapers_health(
    days: int = 7, session: AsyncSession = Depends(get_async_session)
):
    """
    Provides detailed health metrics for all scrapers based on logs.
    """
    health_service = ScraperHealthService(session)
    return await health_service.get_store_health_metrics(days=days)


@router.get("/admin/scrapers/health/summary")
async def get_scrapers_health_summary(
    session: AsyncSession = Depends(get_async_session)
):
    """
    Provides a high-level summary of the entire scraping system health.
    """
    health_service = ScraperHealthService(session)
    return await health_service.get_system_health_summary()


@router.post("/admin/scrapers/{store_name}/reset")
async def reset_scraper_circuit_breaker(
    store_name: str, session: AsyncSession = Depends(get_async_session)
):
    """
    Resets the circuit breaker for a specific store.
    """
    health_service = ScraperHealthService(session)
    await health_service.reset_store_circuit_breaker(store_name)
    return {"message": f"Circuit breaker for {store_name} reset successfully."}


@router.get("/deals")
async def list_deals(
    sort_by: Optional[str] = Query(
        None, enum=["category", "effective_discount", "discount_pct", "distance"]
    ),
    postal_code: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
):
    """
    List all active deals with product and store info.
    Sort by 'category', 'effective_discount', 'discount_pct', or 'distance'.
    Filter by proximity if postal_code is provided.
    """
    statement = select(Deal, Product, Store).join(Product).join(Store)

    # Sorting by category is done at the DB level for efficiency
    if sort_by == "category":
        statement = statement.order_by(Product.category)

    result = await session.execute(statement)
    results = result.all()

    deals_data = []
    for deal, product, store in results:
        distance = None
        if postal_code:
            distance = GeospatialService.get_distance_between_postal_codes(
                postal_code, store.postal_code
            )
            # Filter by 5km radius if distance calculation was successful
            if distance is not None and distance > 5.0:
                continue

        deal_item = {
            "id": deal.id,
            "product": product,
            "store": store,
            "price": deal.price,
            "original_price": deal.original_price,
            "discount_pct": deal.discount_pct,
            "valid_until": deal.valid_until,
            "loyalty_program": deal.loyalty_program,
            "loyalty_points": deal.loyalty_points,
            "is_stale": store.is_stale,
            "image_url": deal.image_url,
            "sale_info": deal.sale_info,
            "distance": round(distance, 1) if distance is not None else None,
        }

        # Calculate effective price for sorting and display
        effective_price = deal.price
        if deal.loyalty_program and deal.loyalty_points:
            point_value = LOYALTY_POINT_VALUES.get(deal.loyalty_program, 0)
            effective_price -= deal.loyalty_points * point_value

        deal_item["effective_price"] = round(effective_price, 2)
        deals_data.append(deal_item)

    # In-memory sorting for calculated fields
    if sort_by == "effective_discount":
        deals_data.sort(key=lambda x: (x["effective_price"], x["price"]))
    elif sort_by == "discount_pct":
        deals_data.sort(key=lambda x: x.get("discount_pct") or 0, reverse=True)
    elif sort_by == "distance":
        deals_data.sort(key=lambda x: x.get("distance") if x.get("distance") is not None else float('inf'))

    return deals_data


@router.post("/plans/generate")
async def generate_meal_plan(user_id: int, model: Optional[str] = None):
    """
    Triggers meal plan generation in the background.
    Returns a task_id to poll.
    """
    task = generate_meal_plan_task.delay(user_id, model_type=model)
    return {"task_id": task.id, "status": "Processing"}


class RegenerateMealRequest(BaseModel):
    user_id: int
    day: str
    type: str
    dietary_preferences: List[str]
    existing_meals: List[Dict[str, Any]]
    model_type: Optional[str] = None


@router.post("/plans/regenerate-meal")
async def regenerate_meal(
    request: RegenerateMealRequest, session: AsyncSession = Depends(get_async_session)
):
    """
    Generates a new, single meal to replace an existing one in a meal plan.
    """
    user = await session.get(User, request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    llm_service = LLMService(session)
    new_meal = await llm_service.regenerate_single_meal(
        user=user,
        day=request.day,
        meal_type=request.type,
        dietary_preferences=request.dietary_preferences,
        existing_meals=request.existing_meals,
        model_type=request.model_type,
    )

    if not new_meal:
        raise HTTPException(
            status_code=500, detail="Failed to generate a new meal from the meal plan."
        )

    return new_meal


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    Checks the status of a background task.
    """
    task_result = AsyncResult(task_id)
    if task_result.state == "PENDING":
        return {"task_id": task_id, "status": "Pending"}
    elif task_result.state == "REVOKED":
        return {"task_id": task_id, "status": "Stopped"}
    elif task_result.state != "FAILURE":
        return {
            "task_id": task_id,
            "status": task_result.state,
            "result": task_result.result,
        }
    else:
        # something went wrong in the background job
        return {"task_id": task_id, "status": "Failed", "error": str(task_result.info)}


@router.post("/tasks/{task_id}/stop")
async def stop_task(task_id: str):
    """
    Revokes/stops a running background task.
    """
    from app.celery_app import celery_app

    celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
    return {
        "task_id": task_id,
        "status": "Stopped",
        "message": "Task revocation requested",
    }


@router.get("/plans/{user_id}/latest")
async def get_latest_plan(
    user_id: int, session: AsyncSession = Depends(get_async_session)
):
    statement = (
        select(MealPlan)
        .where(MealPlan.user_id == user_id)
        .order_by(MealPlan.created_at.desc())
    )
    result = await session.execute(statement)  # Changed exec to execute
    plan = (
        result.scalars().first()
    )  # scalars() needed for getting the objects directly if select(MealPlan)
    if not plan or not plan.content_json:
        raise HTTPException(status_code=404, detail="No plan found or plan is empty.")

    plan_data = json.loads(plan.content_json)
    plan_data["id"] = plan.id  # Include the meal plan ID for feedback
    return plan_data


@router.get("/shopping/optimize")
async def optimize_shopping_list(
    user_id: int,
    strategy: str = "min_cost",
    preferred_stores: Optional[List[str]] = Query(None),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Returns the optimized shopping list for the user's latest meal plan.
    """
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get latest plan
    statement = (
        select(MealPlan)
        .where(MealPlan.user_id == user_id)
        .order_by(MealPlan.created_at.desc())
    )
    result = await session.execute(statement)
    plan = result.scalars().first()

    if not plan:
        raise HTTPException(
            status_code=404, detail="No meal plan found. Generate one first."
        )

    plan_data = json.loads(plan.content_json)

    optimizer = ShoppingListOptimizer(session)  # Passing async session
    result = await optimizer.generate_shopping_list_async(user, plan_data, strategy, preferred_stores)

    return result


@router.get("/pantry/{user_id}", response_model=List[PantryItemRead])
async def get_pantry_items(
    user_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    items = await PantryService.list_items(session, user_id)
    return [PantryItemRead.model_validate(i) for i in items]


@router.post("/pantry/{user_id}/add", response_model=List[PantryItemRead])
async def add_pantry_items(
    user_id: int,
    request: PantryAddRequest,
    session: AsyncSession = Depends(get_async_session),
):
    # Pantry starts empty; user-selected items populate it.
    updated = await PantryService.add_items(
        session,
        user_id,
        [i.model_dump() for i in request.items],
    )
    return [PantryItemRead.model_validate(i) for i in updated]


@router.delete("/pantry/{user_id}/{item_id}")
async def delete_pantry_item(
    user_id: int,
    item_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    item = await session.get(PantryItem, item_id)
    if not item or item.user_id != user_id:
        raise HTTPException(status_code=404, detail="Pantry item not found")
    await session.delete(item)
    await session.commit()
    return {"message": "Pantry item deleted"}


@router.post("/pantry/{user_id}/consume-latest-plan")
async def consume_pantry_from_latest_plan(
    user_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # "Remove them as soon as they are in a meal": consume pantry based on the latest plan's ingredients.
    return await PantryService.consume_from_latest_plan(
        session,
        user_id=user_id,
        household_size=user.household_size,
    )


@router.post("/feedback", response_model=FeedbackRead)
async def create_feedback(
    feedback_in: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    feedback = Feedback(
        user_id=current_user.id,
        recipe_id=feedback_in.recipe_id,
        meal_plan_id=feedback_in.meal_plan_id,
        rating=feedback_in.rating,
        comment=feedback_in.comment,
    )
    session.add(feedback)
    await session.commit()
    await session.refresh(feedback)
    return feedback


@router.get("/feedback", response_model=List[FeedbackRead])
async def list_feedback(
    recipe_id: Optional[int] = None,
    meal_plan_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    statement = select(Feedback).where(Feedback.user_id == current_user.id)
    if recipe_id:
        statement = statement.where(Feedback.recipe_id == recipe_id)
    if meal_plan_id:
        statement = statement.where(Feedback.meal_plan_id == meal_plan_id)

    statement = statement.order_by(Feedback.created_at.desc())
    result = await session.execute(statement)
    return result.scalars().all()


@router.get("/feedback/summary")
async def get_feedback_summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    # Get average rating for recipes and meal plans
    recipe_avg_result = await session.execute(
        select(func.avg(Feedback.rating)).where(
            Feedback.user_id == current_user.id, Feedback.recipe_id.is_not(None)
        )
    )
    recipe_avg = recipe_avg_result.scalar()

    meal_plan_avg_result = await session.execute(
        select(func.avg(Feedback.rating)).where(
            Feedback.user_id == current_user.id, Feedback.meal_plan_id.is_not(None)
        )
    )
    meal_plan_avg = meal_plan_avg_result.scalar()

    total_count_result = await session.execute(
        select(func.count(Feedback.id)).where(Feedback.user_id == current_user.id)
    )
    total_count = total_count_result.scalar()

    return {
        "average_recipe_rating": float(recipe_avg) if recipe_avg is not None else 0,
        "average_meal_plan_rating": float(meal_plan_avg) if meal_plan_avg is not None else 0,
        "total_feedback_count": total_count or 0,
    }
