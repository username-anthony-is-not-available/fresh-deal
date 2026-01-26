import json
from celery import shared_task
from app.celery_app import celery_app
from sqlmodel import Session, select
from app.core.db import engine
from app.models.all_models import User, MealPlan, Store, Product, Deal
from app.agents.planner_agent import MealPlannerAgent
from app.agents.scraper_agent import ScraperAgent
from app.services.pantry_service import PantryService
from datetime import datetime, timedelta, date
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
    with Session(engine) as session:
        try:
            scraper_agent = ScraperAgent(session, postal_code)

            loop = _get_or_create_event_loop()
            deals = loop.run_until_complete(
                scraper_agent.scrape(stores, limit_per_store)
            )

            if not deals:
                return {"status": "No deals found", "count": 0}

            scraper_agent.persist_deals(deals)

            return {
                "status": "Success",
                "scraped_items": len(deals),
            }

        except Exception as e:
            import traceback

            traceback.print_exc()
            return {"error": str(e)}


@shared_task
def generate_meal_plan_task(user_id: int):
    # Tasks run in a separate process, so they need their own sync session
    with Session(engine) as session:
        try:
            user = session.get(User, user_id)
            if not user:
                return {"error": "User not found"}

            planner = MealPlannerAgent(session)
            plan_data = planner.generate_plan(user)

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
