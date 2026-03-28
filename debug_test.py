import asyncio
import traceback
from unittest.mock import AsyncMock, patch
from app.models.all_models import Deal, Store, Product, SQLModel, ScraperLog
from sqlmodel import select, Session
from app.core.db import engine, async_engine
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.scraper_agent import ScraperAgent

async def run_debug():
    try:
        # Create tables
        async with async_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
            await conn.run_sync(SQLModel.metadata.create_all)

        mock_deals = [
            {
                "name": "Test Apple",
                "price": 1.99,
                "original_price": 2.99,
                "unit": "lb",
                "store": "Provigo",
                "category": "Produce",
                "image_url": "http://example.com/apple.jpg",
                "valid_from": None,
                "valid_until": None,
                "loyalty_program": None,
                "loyalty_points": None,
                "sale_info": "Save .00"
            }
        ]

        async with AsyncSession(async_engine) as session:
            store = Store(name="Provigo", chain="Provigo", postal_code="H4T1V6")
            session.add(store)
            await session.commit()

        with patch("app.services.scraper_bridge_service.ScraperBridgeService.run_root_scraper", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_deals

            async with AsyncSession(async_engine) as session:
                scraper_agent = ScraperAgent(session, "H4T1V6")
                deals_by_store = await scraper_agent.scrape_with_root_framework(["provigo"], 1)
                await scraper_agent.persist_deals(deals_by_store["provigo"])
                await session.commit()
        print("Success!")
    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.join(os.getcwd(), "smart-meal-planner/backend"))
    os.environ["USE_SQLITE_LOCAL"] = "True"
    os.environ["USE_MOCK_AI"] = "True"
    asyncio.run(run_debug())
