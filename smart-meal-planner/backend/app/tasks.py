
import json
from celery import shared_task
from app.celery_app import celery_app
from sqlmodel import Session, select
from app.core.db import engine
from app.models.all_models import User, MealPlan, Store, Product, Deal
from app.agents.planner_agent import MealPlannerAgent
from app.agents.metro_scraper import MetroScraper
from app.agents.flipp_scraper import FlippScraper, CANADIAN_STORES
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


@shared_task(rate_limit='10/m')
def scrape_flipp_task(
    stores: list = None,
    postal_code: str = "H4T1V6",
    limit: int = 100
):
    """
    Background task to scrape grocery deals from Flipp API.
    
    This is the RECOMMENDED scraper as it:
    - Uses a public API (no bot protection issues)
    - Gets data from multiple stores at once
    - Is much faster and more reliable than browser scraping
    
    Args:
        stores: List of store keys (e.g., ["metro", "maxi", "walmart"])
                If None, scrapes all available stores
        postal_code: Canadian postal code for location-based deals
        limit: Maximum number of items to fetch
    """
    with Session(engine) as session:
        try:
            # Run Flipp scraper
            scraper = FlippScraper(
                postal_code=postal_code,
                stores=stores
            )
            
            loop = _get_or_create_event_loop()
            items = loop.run_until_complete(scraper.scrape(limit=limit))

            if not items:
                return {"status": "No items found", "count": 0}

            # Persist Data - group by store
            store_cache = {}  # Cache store objects by name
            new_products = 0
            new_deals = 0
            today = date.today()
            
            for item in items:
                store_name = item.get("store", "Unknown Store")
                
                # Get or create store
                if store_name not in store_cache:
                    store = session.exec(
                        select(Store).where(Store.name == store_name)
                    ).first()
                    if not store:
                        # Try to find chain info
                        chain = store_name
                        store = Store(
                            name=store_name,
                            chain=chain,
                            postal_code=postal_code,
                            address="Online"
                        )
                        session.add(store)
                        session.commit()
                        session.refresh(store)
                    store_cache[store_name] = store
                
                store = store_cache[store_name]

                # Find or Create Product
                product = session.exec(
                    select(Product).where(Product.name == item["name"])
                ).first()
                if not product:
                    product = Product(
                        name=item["name"],
                        category=item.get("category", "Grocery"),
                        unit_type=item.get("unit", "each")
                    )
                    session.add(product)
                    session.commit()
                    session.refresh(product)
                    new_products += 1

                # Parse validity dates if available
                valid_from = today
                valid_until = today + timedelta(days=7)
                
                if item.get("valid_from"):
                    try:
                        valid_from = datetime.fromisoformat(
                            item["valid_from"].replace("Z", "+00:00")
                        ).date()
                    except:
                        pass
                        
                if item.get("valid_to"):
                    try:
                        valid_until = datetime.fromisoformat(
                            item["valid_to"].replace("Z", "+00:00")
                        ).date()
                    except:
                        pass

                # Calculate discount percentage
                original = item.get("original_price", item["price"])
                discount_pct = 0
                if original > 0 and original > item["price"]:
                    discount_pct = round((original - item["price"]) / original * 100, 1)

                # Create Deal
                deal = Deal(
                    product_id=product.id,
                    store_id=store.id,
                    price=item["price"],
                    original_price=original,
                    discount_pct=discount_pct,
                    valid_from=valid_from,
                    valid_until=valid_until
                )
                session.add(deal)
                new_deals += 1

            session.commit()

            # Summary by store
            store_summary = {}
            for item in items:
                store = item.get("store", "Unknown")
                store_summary[store] = store_summary.get(store, 0) + 1

            return {
                "status": "Success",
                "source": "Flipp API",
                "scraped_items": len(items),
                "new_products": new_products,
                "new_deals": new_deals,
                "stores": store_summary
            }

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e)}


# Rate limit: max 2 scrape tasks per minute to avoid hammering external sites
@shared_task(rate_limit='2/m')
def scrape_metro_task(limit: int = 50):
    """
    Background task to scrape Metro.ca using browser automation.
    
    NOTE: This scraper often gets blocked by Cloudflare protection.
    For more reliable results, use scrape_flipp_task() instead.
    """
    with Session(engine) as session:
        try:
            # 1. Run Scraper (Async needs to be run in sync context)
            scraper = MetroScraper()
            loop = _get_or_create_event_loop()

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
