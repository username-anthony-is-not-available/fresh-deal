
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_async_session, get_session
from sqlmodel import Session
from app.models.all_models import User, MealPlan, Deal, Product, Store
from app.agents.scraper_agent import MockScraperAgent
from app.agents.flipp_scraper import CANADIAN_STORES
from app.services.shopping_optimizer import ShoppingListOptimizer
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from celery.result import AsyncResult
import json
from datetime import datetime, timedelta
from app.tasks import generate_meal_plan_task, scrape_metro_task, scrape_flipp_task
from app.services.user_service import UserService
from app.schemas import UserUpdate, UserRead

router = APIRouter()

class UserCreate(BaseModel):
    postal_code: str
    household_size: int
    dietary_preferences: str

@router.post("/onboard")
async def onboard_user(user_in: UserCreate, session: AsyncSession = Depends(get_async_session)):
    user = User(
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

@router.post("/data/seed")
def seed_data(session: Session = Depends(get_session)):
    # Keep synchronous as it's a dev tool and uses MockScraperAgent which might be sync
    scraper = MockScraperAgent(session)
    count = scraper.generate_deals()
    return {"message": f"Seeded database with {count} deals."}

@router.post("/admin/scrape/metro")
async def trigger_metro_scrape(limit: int = 50):
    """
    Triggers the background task to scrape Metro.ca using browser automation.
    
    NOTE: This often gets blocked by Cloudflare. 
    Use /admin/scrape/flipp instead for more reliable results.
    """
    task = scrape_metro_task.delay(limit)
    return {"task_id": task.id, "status": "Processing", "scraper": "metro-playwright"}


class FlippScrapeRequest(BaseModel):
    """Request body for Flipp scraping."""
    stores: Optional[List[str]] = None
    postal_code: str = "H4T1V6"
    limit: int = 100


@router.post("/admin/scrape/flipp")
async def trigger_flipp_scrape(request: FlippScrapeRequest = None):
    """
    Triggers the background task to scrape grocery deals from Flipp API.
    
    This is the RECOMMENDED scraper as it uses a public API and doesn't
    get blocked like browser-based scrapers.
    
    Available stores:
    - metro, maxi, provigo, super_c, loblaws, walmart, 
    - food_basics, iga, no_frills, real_canadian_superstore
    
    Example: {"stores": ["metro", "walmart"], "postal_code": "H4T1V6", "limit": 100}
    """
    if request is None:
        request = FlippScrapeRequest()
        
    task = scrape_flipp_task.delay(
        stores=request.stores,
        postal_code=request.postal_code,
        limit=request.limit
    )
    return {
        "task_id": task.id, 
        "status": "Processing", 
        "scraper": "flipp-api",
        "stores": request.stores or list(CANADIAN_STORES.keys()),
        "postal_code": request.postal_code
    }


@router.get("/admin/scrapers")
async def list_scrapers():
    """
    List available scrapers and their configurations.
    """
    return {
        "scrapers": [
            {
                "id": "flipp",
                "name": "Flipp API",
                "description": "Uses the Flipp public API to get flyer deals. Most reliable option.",
                "endpoint": "/admin/scrape/flipp",
                "method": "POST",
                "recommended": True,
                "stores": {key: store.name for key, store in CANADIAN_STORES.items()}
            },
            {
                "id": "metro",
                "name": "Metro Playwright",
                "description": "Uses Playwright browser automation. Often blocked by Cloudflare.",
                "endpoint": "/admin/scrape/metro",
                "method": "POST",
                "recommended": False,
                "stores": {"metro": "Metro"}
            }
        ]
    }

@router.get("/deals")
async def list_deals(session: AsyncSession = Depends(get_async_session)):
    """List all active deals with product and store info."""
    # Join Deal, Product, Store
    statement = select(Deal, Product, Store).join(Product).join(Store)
    result = await session.execute(statement) # Changed exec to execute
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
            "valid_until": deal.valid_until
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
