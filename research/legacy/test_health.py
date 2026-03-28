import asyncio
import sys
import os
from datetime import datetime, timedelta, timezone

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'smart-meal-planner/backend'))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlmodel import SQLModel, select
from app.models.all_models import ScraperLog
from app.services.scraper_health_service import ScraperHealthService

async def test_health_service():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSession(engine) as session:
        # Add some mock logs
        logs = [
            ScraperLog(store_name="Metro", status="success", items_scraped=10, duration_seconds=5.0, timestamp=datetime.now(timezone.utc) - timedelta(hours=1)),
            ScraperLog(store_name="Metro", status="success", items_scraped=12, duration_seconds=4.5, timestamp=datetime.now(timezone.utc) - timedelta(hours=2)),
            ScraperLog(store_name="Walmart", status="failure", items_scraped=0, duration_seconds=30.0, error_message="Timeout", timestamp=datetime.now(timezone.utc) - timedelta(hours=1)),
            ScraperLog(store_name="Walmart", status="failure", items_scraped=0, duration_seconds=30.0, error_message="Timeout", timestamp=datetime.now(timezone.utc) - timedelta(hours=2)),
            ScraperLog(store_name="Walmart", status="failure", items_scraped=0, duration_seconds=30.0, error_message="Timeout", timestamp=datetime.now(timezone.utc) - timedelta(hours=3)),
            ScraperLog(store_name="IGA", status="success", items_scraped=5, duration_seconds=10.0, timestamp=datetime.now(timezone.utc) - timedelta(hours=5)),
            ScraperLog(store_name="IGA", status="failure", items_scraped=0, duration_seconds=15.0, error_message="Selector missing", timestamp=datetime.now(timezone.utc) - timedelta(hours=1)),
        ]
        for l in logs:
            session.add(l)
        await session.commit()

        health_service = ScraperHealthService(session)
        metrics = await health_service.get_store_health_metrics()

        print("\n--- Store Health Metrics ---")
        for m in metrics:
            print(f"Store: {m['store_name']:10} | Success: {m['success_rate']}% | Status: {m['status']:10} | Failures: {m['consecutive_failures']}")

        summary = await health_service.get_system_health_summary()
        print("\n--- System Summary ---")
        print(f"Status: {summary['overall_status']}")
        print(f"Success Rate: {summary['overall_success_rate']}%")
        print(f"Healthy: {summary['healthy_scrapers']}/{summary['total_scrapers']}")
        print(f"Critical: {summary['critical_scrapers']}")

if __name__ == "__main__":
    asyncio.run(test_health_service())
