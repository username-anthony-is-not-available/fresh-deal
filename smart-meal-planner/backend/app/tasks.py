
import json
from celery import shared_task
from app.celery_app import celery_app
from sqlmodel import Session, select
from app.core.db import engine
from app.models.all_models import User, MealPlan, Store, Product, Deal
from app.agents.planner_agent import MealPlannerAgent
from app.agents.metro_scraper import MetroScraper
from datetime import datetime, timedelta, date
import asyncio

@shared_task
def scrape_metro_task(limit: int = 50):
    """
    Background task to scrape Metro.ca and update the database.
    """
    with Session(engine) as session:
        try:
            # 1. Run Scraper (Async needs to be run in sync context)
            scraper = MetroScraper()
            # Celery workers use prefork, asyncio might need new loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            items = loop.run_until_complete(scraper.scrape(limit=limit))

            if not items:
                return {"status": "No items found", "count": 0}

            # 2. Persist Data
            # Ensure Store exists
            store = session.exec(select(Store).where(Store.name == "Metro Online")).first()
            if not store:
                store = Store(
                    name="Metro Online",
                    chain="Metro",
                    postal_code="H4T 1V6", # Default for POC
                    address="Online"
                )
                session.add(store)
                session.commit()
                session.refresh(store)

            new_products = 0
            new_deals = 0
            today = date.today()
            next_week = today + timedelta(days=7)

            for item in items:
                # Find or Create Product
                # Simple name matching for POC
                product = session.exec(select(Product).where(Product.name == item["name"])).first()
                if not product:
                    product = Product(
                        name=item["name"],
                        category=item["category"],
                        unit_type=item["unit"]
                    )
                    session.add(product)
                    session.commit()
                    session.refresh(product)
                    new_products += 1

                # Create Deal (Price)
                # We overwrite or create new? Let's just create new deal entries for "this week"
                # Check if deal exists for this product/store/week?
                # For POC, just add.
                deal = Deal(
                    product_id=product.id,
                    store_id=store.id,
                    price=item["price"],
                    original_price=item["original_price"],
                    discount_pct=0, # Calculate if needed
                    valid_from=today,
                    valid_until=next_week
                )
                session.add(deal)
                new_deals += 1

            session.commit()

            return {
                "status": "Success",
                "scraped_items": len(items),
                "new_products": new_products,
                "new_deals": new_deals
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
                content_json=json.dumps(plan_data)
            )
            session.add(meal_plan)
            session.commit()
            session.refresh(meal_plan)

            # Return just the ID or basic info, or the full plan
            # The result is stored in Redis
            return json.loads(meal_plan.content_json)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e)}
