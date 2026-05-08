import pytest
import pytest_asyncio
from app.agents.scraper_agent import ScraperAgent
from app.models.all_models import Deal, PriceRecord
from sqlmodel import SQLModel, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from unittest.mock import patch, MagicMock

# In-memory SQLite database for testing
async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")

async def setup_async_database():
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

@pytest_asyncio.fixture
async def async_session():
    await setup_async_database()
    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        yield session
    # Cleanup between tests
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

@pytest.mark.asyncio
async def test_price_history_and_enriched_data(async_session):
    scraper_agent = ScraperAgent(async_session)

    # Initial scrape - Product A at Store X
    deals_v1 = [
        {
            "name": "Product A",
            "store": "Store X",
            "price": 10.0,
            "category": "Test",
            "image_url": "http://example.com/a.jpg",
            "sale_info": "Special offer"
        }
    ]

    await scraper_agent.persist_deals(deals_v1, commit=True)

    # Verify Deal and PriceRecord
    result = await async_session.execute(select(Deal))
    deal = result.scalars().first()
    assert deal.price == 10.0
    assert deal.image_url == "http://example.com/a.jpg"
    assert deal.sale_info == "Special offer"

    result = await async_session.execute(select(PriceRecord))
    records = result.scalars().all()
    assert len(records) == 1
    assert records[0].price == 10.0

    # Second scrape - Price changed
    deals_v2 = [
        {
            "name": "Product A",
            "store": "Store X",
            "price": 9.0,
            "category": "Test",
            "image_url": "http://example.com/a.jpg",
            "sale_info": "Even better"
        }
    ]

    # Mock deal_quality_service to see if it receives history
    with patch("app.agents.scraper_agent.deal_quality_service.score_deal") as mock_score:
        # Need to return a valid QualityScore mock
        mock_quality = MagicMock()
        mock_quality.quality.value = "excellent"
        mock_quality.overall_score = 90.0
        mock_score.return_value = mock_quality

        await scraper_agent.persist_deals(deals_v2, commit=True)

        # Verify history was passed
        args, kwargs = mock_score.call_args
        assert "historical_prices" in kwargs
        assert kwargs["historical_prices"] == [10.0]

    # Verify Deal updated and new PriceRecord added
    result = await async_session.execute(select(Deal))
    deals = result.scalars().all()
    # ScraperAgent.persist_deals updates the deal if same product/store/price/validity,
    # but here price changed, so it might add a new one or we might need to check how duplicates are handled.
    # Actually, existing_deals_cache uses (product_id, store_id, price, valid_until).
    # Since price changed, it's a new entry in existing_deals_cache.
    assert len(deals) == 2

    result = await async_session.execute(select(PriceRecord))
    records = result.scalars().all()
    assert len(records) == 2
    assert records[1].price == 9.0

@pytest.mark.asyncio
async def test_no_duplicate_price_record(async_session):
    scraper_agent = ScraperAgent(async_session)

    deals = [
        {"name": "Product B", "store": "Store Y", "price": 5.0, "category": "Test"}
    ]

    await scraper_agent.persist_deals(deals, commit=True)
    await scraper_agent.persist_deals(deals, commit=True)

    # Should only have 1 PriceRecord for the same price
    result = await async_session.execute(select(PriceRecord))
    records = result.scalars().all()
    assert len(records) == 1
