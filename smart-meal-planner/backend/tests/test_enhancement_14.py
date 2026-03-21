import pytest
import pytest_asyncio
from app.agents.scraper_agent import ScraperAgent
from app.agents.scrapers.base_scraper import BaseScraper
from app.models.all_models import Store, Product, Deal, ScraperLog
from sqlmodel import SQLModel, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

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

class MockScraper(BaseScraper):
    async def _scrape_page(self, page, limit):
        return []

@pytest.mark.asyncio
async def test_bulk_persistence(async_session):
    scraper_agent = ScraperAgent(async_session)

    deals = [
        {"name": "New Product A", "store": "New Store X", "price": 10.0, "category": "Test"},
        {"name": "New Product B", "store": "New Store X", "price": 15.0, "category": "Test"},
        {"name": "New Product A", "store": "New Store Y", "price": 11.0, "category": "Test"},
    ]

    await scraper_agent.persist_deals(deals, commit=True)

    # Verify stores added
    result = await async_session.execute(select(Store).where(Store.name.in_(["New Store X", "New Store Y"])))
    stores = result.scalars().all()
    assert len(stores) == 2

    # Verify products added
    result = await async_session.execute(select(Product).where(Product.name.in_(["New Product A", "New Product B"])))
    products = result.scalars().all()
    assert len(products) == 2

    # Verify deals added
    result = await async_session.execute(select(Deal))
    deals_db = result.scalars().all()
    assert len(deals_db) == 3

def test_enhanced_price_parsing():
    scraper = MockScraper()

    # Standard
    assert scraper._parse_price("$2.99") == 2.99
    assert scraper._parse_price("2,99$") == 2.99

    # Multi-buy (French and English)
    assert scraper._parse_price("2 pour 5.00$") == 2.50
    assert scraper._parse_price("3 for $9") == 3.0
    assert scraper._parse_price("2/$5.00") == 2.50

    # Reverse multi-buy
    assert scraper._parse_price("5.00$ / 2") == 2.50
    assert scraper._parse_price("$6 ea. 3") == 2.0

    # Cent prices
    assert scraper._parse_price("88¢") == 0.88
    assert scraper._parse_price("99c") == 0.99

@pytest.mark.asyncio
async def test_scraper_logging(async_session):
    scraper_agent = ScraperAgent(async_session)

    # Trigger a log
    await scraper_agent._log_scrape("Test Store", "success", 10, 5.5, None)
    await async_session.commit()

    # Verify log in DB
    result = await async_session.execute(select(ScraperLog).where(ScraperLog.store_name == "Test Store"))
    logs = result.scalars().all()
    assert len(logs) == 1
    assert logs[0].status == "success"
    assert logs[0].items_scraped == 10
    assert logs[0].duration_seconds == 5.5

def test_enhanced_unit_extraction():
    scraper = MockScraper()

    assert scraper._extract_unit("Apples $2.99/lb") == "lb"
    assert scraper._extract_unit("Steak par kg") == "kg"
    assert scraper._extract_unit("Yogurt 100 g") == "100g"
    assert scraper._extract_unit("Milk 1L") == "L"
    assert scraper._extract_unit("Eggs 12 pack") == "each"
