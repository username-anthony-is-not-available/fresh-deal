import json
from celery import shared_task, group
from sqlmodel import Session, select
from sqlalchemy import func, delete
from app.core.db import engine, async_engine
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.all_models import User, MealPlan, Store, Deal, ScraperLog, PriceRecord
from app.agents.planner_agent import MealPlannerAgent
from app.agents.scraper_agent import ScraperAgent
from app.services.pantry_service import PantryService
from app.services.deal_service import DealService
from app.services.notification_service import NotificationService
from app.core.config import settings
from datetime import datetime, timedelta, date, timezone
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


@shared_task(bind=True, rate_limit="10/m")
def scrape_store_task(
    self, store_name: str, postal_code: str = "H4T1V6", limit_per_store: int = 50, scraper_type: str = "default"
):
    """
    Granular task to scrape a single store. This allows for parallelization across workers.
    """
    loop = _get_or_create_event_loop()

    async def run_scrape():
        async with AsyncSession(async_engine) as session:
            try:
                scraper_agent = ScraperAgent(session, postal_code)
                result = await scraper_agent.scrape_and_persist_single_store(
                    store_name, limit=limit_per_store, scraper_type=scraper_type
                )
                return result
            except Exception as e:
                import traceback
                traceback.print_exc()
                return {"store": store_name, "error": str(e)}

    return loop.run_until_complete(run_scrape())


@shared_task
def scrape_task(
    stores: list = None, postal_code: str = "H4T1V6", limit_per_store: int = 50
):
    """
    Orchestrator task that parallelizes scraping across multiple stores using Celery group.
    """
    if not stores:
        stores = settings.SUPPORTED_STORES

    job = group(
        scrape_store_task.s(store, postal_code, limit_per_store)
        for store in stores
    )
    result = job.apply_async()
    return {"status": "Dispatched", "group_id": result.id, "stores": stores}


@shared_task
def sync_root_scrapers_task(
    stores: list = None, postal_code: str = "H4T1V6", limit_per_store: int = 50
):
    """
    Orchestrator task for root framework scrapers, parallelized using Celery group.
    """
    if not stores:
        from app.services.scraper_bridge_service import ScraperBridgeService
        target_stores = list(ScraperBridgeService.SCRAPER_MAP.keys())
    else:
        target_stores = stores

    if not target_stores:
        return {"status": "No root scrapers configured", "count": 0}

    job = group(
        scrape_store_task.s(store, postal_code, limit_per_store, scraper_type="root_framework")
        for store in target_stores
    )
    result = job.apply_async()
    return {"status": "Dispatched", "group_id": result.id, "stores": target_stores}


@shared_task
def cleanup_old_data_task():
    """
    Task to prune old database records to maintain performance.
    - Deletes ScraperLog entries older than 30 days.
    - Deletes expired Deal entries older than 14 days.
    """
    with Session(engine) as session:
        try:
            now = datetime.now(timezone.utc)
            log_cutoff = now - timedelta(days=30)
            deal_cutoff = now.date() - timedelta(days=14)

            # Bulk Prune ScraperLogs
            log_del_stmt = delete(ScraperLog).where(ScraperLog.timestamp < log_cutoff)
            log_result = session.execute(log_del_stmt)
            logs_deleted = log_result.rowcount

            # Bulk Prune expired Deals
            deal_del_stmt = delete(Deal).where(Deal.valid_until < deal_cutoff)
            deal_result = session.execute(deal_del_stmt)
            deals_deleted = deal_result.rowcount

            # Bulk Prune old PriceRecords (older than 90 days)
            price_cutoff = now - timedelta(days=90)
            price_del_stmt = delete(PriceRecord).where(PriceRecord.timestamp < price_cutoff)
            price_result = session.execute(price_del_stmt)
            prices_deleted = price_result.rowcount

            session.commit()
            return {
                "status": "Success",
                "logs_deleted": logs_deleted,
                "deals_deleted": deals_deleted,
                "prices_deleted": prices_deleted,
            }
        except Exception as e:
            return {"error": str(e)}


@shared_task
def generate_meal_plan_task(user_id: int, model_type: Optional[str] = None):
    # Tasks run in a separate process, so they need their own sync session
    with Session(engine) as session:
        try:
            # Automated "fresh-deal" Enhancement: Check for stale stores
            # and trigger a background refresh if needed.
            stale_stores = session.exec(select(Store)).all()
            stale_chains = [s.chain for s in stale_stores if s.is_stale]

            user = session.get(User, user_id)
            if not user:
                return {"error": "User not found"}

            # Check for active deals count efficiently
            total_active = session.exec(
                select(func.count(Deal.id)).where(Deal.valid_until >= date.today())
            ).one()

            if stale_chains or total_active < 20:
                from celery.utils.log import get_task_logger
                logger = get_task_logger(__name__)

                if total_active < 20:
                    logger.info(f"Insufficient active deals ({total_active}). Forcing synchronous refresh for postal code {user.postal_code}.")
                    # Run a quick scrape for a few stores synchronously to ensure we have data
                    loop = _get_or_create_event_loop()
                    async def quick_refresh():
                        async with AsyncSession(async_engine) as async_session:
                            scraper = ScraperAgent(async_session, postal_code=user.postal_code)
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
                        f"Stale deals detected for {len(stale_chains)} stores: {stale_chains}. Triggering background refresh for postal code {user.postal_code}."
                    )
                    scrape_task.delay(stores=stale_chains, postal_code=user.postal_code)

            planner = MealPlannerAgent(session)
            plan_data = planner.generate_plan(user, model_type=model_type)

            # Enrich with nutrition data
            try:
                from app.agents.nutrition_agent import NutritionAgent
                nutrition_agent = NutritionAgent(session=session)
                loop = _get_or_create_event_loop()
                plan_data = loop.run_until_complete(nutrition_agent.validate_plan(plan_data))

                # Persist DailyNutrition records
                loop.run_until_complete(nutrition_agent.persist_daily_nutrition_from_plan(user_id, plan_data))
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


@shared_task
def send_daily_digests_task():
    """
    Orchestrator task that finds all users who have opted in for the daily digest
    and dispatches individual email tasks for each user.
    """
    loop = _get_or_create_event_loop()

    async def dispatch_digests():
        async with AsyncSession(async_engine) as session:
            try:
                # Fetch only IDs to minimize memory overhead
                statement = select(User.id).where(User.email_digest_enabled == True)
                result = await session.execute(statement)
                user_ids = result.scalars().all()

                if not user_ids:
                    return {"status": "No users to notify"}

                for user_id in user_ids:
                    send_user_digest_email_task.delay(user_id)

                return {"status": "Dispatched", "count": len(user_ids)}
            except Exception as e:
                return {"error": str(e)}

    return loop.run_until_complete(dispatch_digests())


@shared_task
def send_user_digest_email_task(user_id: int):
    """
    Task to send a personalized deals digest email to a single user.
    """
    loop = _get_or_create_event_loop()

    async def run_digest():
        async with AsyncSession(async_engine) as session:
            try:
                user = await session.get(User, user_id)
                if not user or not user.email_digest_enabled:
                    return {"status": "User not found or opted out"}

                deal_service = DealService(session)
                deals = await deal_service.get_top_deals(limit=10, postal_code=user.postal_code)

                if deals:
                    await NotificationService.send_daily_deals_digest(user, deals)
                    return {"status": "Email sent", "email": user.email}

                return {"status": "No deals found", "email": user.email}
            except Exception as e:
                import traceback
                traceback.print_exc()
                return {"error": str(e)}

    return loop.run_until_complete(run_digest())
