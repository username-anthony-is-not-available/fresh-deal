import pytest
from unittest.mock import AsyncMock, patch
from app.models.all_models import Deal, Store, Product, SQLModel, ScraperLog
from sqlmodel import select, Session
from app.core.db import engine, async_engine
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.scraper_agent import ScraperAgent
from datetime import date, timedelta

@pytest.mark.asyncio
async def test_sync_root_scrapers_task_integration():
    """
    Integration test for sync_root_scrapers_task logic.
    Mocks the root scraper to avoid real network calls but tests the agent and database persistence.
    """
    # Create tables
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

    today = date.today()
    mock_deals = [
        {
            "name": "Test Apple",
            "price": 1.99,
            "original_price": 2.99,
            "unit": "lb",
            "store": "Provigo",
            "category": "Produce",
            "image_url": "http://example.com/apple.jpg",
            "valid_from": today,
            "valid_until": today + timedelta(days=7),
            "loyalty_program": None,
            "loyalty_points": None,
            "sale_info": "Save $1.00"
        }
    ]

    # Pre-add the store to ensure it has an ID before persist_deals
    async with AsyncSession(async_engine) as session:
        store = Store(name="Provigo", chain="Provigo", postal_code="H4T1V6")
        session.add(store)
        await session.commit()

    with patch("app.services.scraper_bridge_service.ScraperBridgeService.run_root_scraper", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_deals

        async with AsyncSession(async_engine) as session:
            scraper_agent = ScraperAgent(session, "H4T1V6")
            deals_by_store = await scraper_agent.scrape_with_root_framework(["provigo"], 1)

            assert "provigo" in deals_by_store
            assert len(deals_by_store["provigo"]) == 1

            await scraper_agent.persist_deals(deals_by_store["provigo"])
            await session.commit()

    # Verify database persistence using a separate sync session
    with Session(engine) as session:
        # Re-verify store
        stmt_store = select(Store).where(Store.name == "Provigo")
        store = session.exec(stmt_store).first()
        assert store is not None

        # Re-verify product
        stmt_prod = select(Product).where(Product.name == "Test Apple")
        product = session.exec(stmt_prod).first()
        assert product is not None

        # Verify deal
        stmt = select(Deal).where(Deal.product_id == product.id, Deal.store_id == store.id)
        deal = session.exec(stmt).first()
        assert deal is not None
        assert deal.price == 1.99

        # Verify log
        stmt_log = select(ScraperLog).where(ScraperLog.store_name == "provigo")
        log = session.exec(stmt_log).first()
        assert log is not None
        assert log.status == "success"
        assert log.scraper_type == "root_framework"
