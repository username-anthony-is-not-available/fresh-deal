import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from app.agents.scraper_agent import ScraperAgent
from app.models.all_models import Store, Product, Deal
import asyncio
from unittest.mock import AsyncMock, patch

# In-memory SQLite database for testing
engine = create_engine("sqlite:///:memory:")

def setup_database():
    SQLModel.metadata.create_all(engine)

def teardown_database():
    SQLModel.metadata.drop_all(engine)

@pytest.fixture(name="session")
def session_fixture():
    setup_database()
    with Session(engine) as session:
        yield session
    teardown_database()

@pytest.mark.asyncio
async def test_scraper_agent_orchestration_with_mocked_scrapers(session: Session):
    # Arrange
    agent = ScraperAgent(session)
    stores = ["metro", "walmart"]

    # Mock the scrape methods of the individual scrapers
    with patch('app.agents.scrapers.metro_scraper.MetroScraper.scrape', new_callable=AsyncMock) as mock_metro_scrape, \
         patch('app.agents.scrapers.walmart_scraper.WalmartScraper.scrape', new_callable=AsyncMock) as mock_walmart_scrape:

        mock_metro_scrape.return_value = [{"name": "Metro Product", "price": 1.0, "store": "Metro"}]
        mock_walmart_scrape.return_value = [{"name": "Walmart Product", "price": 2.0, "store": "Walmart"}]

        # Act
        deals = await agent.scrape(stores)

        # Assert
        assert len(deals) == 2
        assert any(d["store"] == "Metro" for d in deals)
        assert any(d["store"] == "Walmart" for d in deals)
        mock_metro_scrape.assert_called_once()
        mock_walmart_scrape.assert_called_once()


def test_persist_deals(session: Session):
    # Arrange
    agent = ScraperAgent(session)
    deals_to_persist = [
        {"name": "Test Product 1", "price": 1.99, "original_price": 2.99, "store": "Test Store", "category": "Test Category", "unit": "each"},
        {"name": "Test Product 2", "price": 0.99, "store": "Test Store", "category": "Test Category", "unit": "kg"},
    ]

    # Act
    agent.persist_deals(deals_to_persist)

    # Assert
    deals = session.exec(select(Deal)).all()
    products = session.exec(select(Product)).all()
    stores = session.exec(select(Store)).all()

    assert len(deals) == 2
    assert len(products) == 2
    assert len(stores) == 1
    assert deals[0].discount_pct == 33
    assert deals[1].original_price == 0.99
