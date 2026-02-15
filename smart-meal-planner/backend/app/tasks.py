import json
from celery import shared_task
from app.celery_app import celery_app
from sqlmodel import Session, select
from sqlalchemy import func
from app.core.db import engine, async_engine
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.all_models import User, MealPlan, Store, Product, Deal
from app.agents.planner_agent import MealPlannerAgent
from app.agents.scraper_agent import ScraperAgent
from app.services.pantry_service import PantryService
from datetime import datetime, timedelta, date
from typing import Optional
import asyncio


def _get_or_create_event_loop():
    """Get existing event loop or create a new one for Celery workers."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Event loop is closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


@shared_task(rate_limit="10/m")
def scrape_task(
    stores: list = None, postal_code: str = "H4T1V6", limit_per_store: int = 50
):
    """
    Background task to scrape grocery deals from a list of stores.
    It uses the ScraperAgent to orchestrate the scraping process, including
    falling back to the Flipp API if direct scraping fails.
    """
    loop = _get_or_create_event_loop()

    async def run_scrape():
        async with AsyncSession(async_engine) as session:
            try:
                scraper_agent = ScraperAgent(session, postal_code)
                deals_by_store = await scraper_agent.scrape(stores, limit_per_store)

                total_deals = 0
                for store_name, store_deals in deals_by_store.items():
                    if store_deals:
                        await scraper_agent.persist_deals(store_deals)
                        total_deals += len(store_deals)

                await session.commit()

                if total_deals == 0:
                    return {"status": "No deals found", "count": 0}

                return {
                    "status": "Success",
                    "scraped_items": total_deals,
                }
            except Exception as e:
                import traceback
                traceback.print_exc()
                return {"error": str(e)}

    return loop.run_until_complete(run_scrape())


@shared_task
def generate_meal_plan_task(user_id: int, model_type: Optional[str] = None):
    # Tasks run in a separate process, so they need their own sync session
    with Session(engine) as session:
        try:
            # Automated "fresh-deal" Enhancement: Check for stale stores
            # and trigger a background refresh if needed.
            stale_stores = session.exec(select(Store)).all()
            stale_chains = [s.chain for s in stale_stores if s.is_stale]

            # Check for active deals count efficiently
            total_active = session.exec(
                select(func.count(Deal.id)).where(Deal.valid_until >= date.today())
            ).one()

            if stale_chains or total_active < 20:
                from celery.utils.log import get_task_logger
                logger = get_task_logger(__name__)

                if total_active < 20:
                    logger.info(f"Insufficient active deals ({total_active}). Forcing synchronous refresh.")
                    # Run a quick scrape for a few stores synchronously to ensure we have data
                    loop = _get_or_create_event_loop()
                    async def quick_refresh():
                        async with AsyncSession(async_engine) as async_session:
                            scraper = ScraperAgent(async_session)
                            # Just scrape 2 major stores with Flipp for speed
                            major_stores = ["walmart", "metro"]
                            results = await scraper.scrape(major_stores, limit_per_store=30)
                            for _, deals in results.items():
                                if deals:
                                    await scraper.persist_deals(deals)

                            await async_session.commit()

                    try:
                        loop.run_until_complete(quick_refresh())
                    except Exception as e:
                        logger.error(f"Quick refresh failed: {e}")

                if stale_chains:
                    logger.info(
                        f"Stale deals detected for {len(stale_chains)} stores: {stale_chains}. Triggering background refresh."
                    )
                    scrape_task.delay(stores=stale_chains)

            user = session.get(User, user_id)
            if not user:
                return {"error": "User not found"}

            planner = MealPlannerAgent(session)
            plan_data = planner.generate_plan(user, model_type=model_type)

            # Enrich with nutrition data
            try:
                from app.agents.nutrition_agent import NutritionAgent
                nutrition_agent = NutritionAgent(session=session)
                loop = _get_or_create_event_loop()
                plan_data = loop.run_until_complete(nutrition_agent.validate_plan(plan_data))
            except Exception as e:
                from celery.utils.log import get_task_logger
                logger = get_task_logger(__name__)
                logger.error(f"Failed to enrich plan with nutrition data: {e}")

            # Extract start date from the first day of the plan
            start_date_str = plan_data.get("meal_plan", [])[0].get("date")
            if start_date_str:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            else:
                # Fallback if somehow missing
                start_date = datetime.now().date()

            meal_plan = MealPlan(
                user_id=user.id,
                start_date=start_date,
                end_date=start_date + timedelta(days=6),
                content_json=json.dumps(plan_data),
            )
            session.add(meal_plan)
            session.commit()
            session.refresh(meal_plan)

            # Pantry behavior (simplified MVP):
            # Pantry starts empty; it is filled by user-selected items.
            # As soon as items appear in generated meals, decrement/remove them.
            try:
                PantryService.consume_from_plan_sync(
                    session,
                    user_id=user.id,
                    household_size=user.household_size,
                    plan_data=plan_data,
                )
            except Exception:
                # Pantry consumption should not fail meal plan generation.
                import traceback

                traceback.print_exc()

            # Return just the ID or basic info, or the full plan
            # The result is stored in Redis
            return json.loads(meal_plan.content_json)

        except Exception as e:
            import traceback

            traceback.print_exc()
            return {"error": str(e)}
