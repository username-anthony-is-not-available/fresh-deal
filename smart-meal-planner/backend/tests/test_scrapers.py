import pytest
from datetime import date
from sqlmodel import Session, SQLModel, create_engine, select
from app.agents.scraper_agent import ScraperAgent
from app.models.all_models import Store, Product, Deal
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from app.agents.scrapers.walmart_scraper import WalmartScraper
from app.agents.scrapers.provigo_scraper import ProvigoScraper
from app.agents.scrapers.iga_scraper import IgaScraper
from app.agents.scrapers.metro_scraper import MetroScraper
import os

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
        assert "metro" in deals
        assert "walmart" in deals
        assert deals["metro"][0]["store"] == "Metro"
        assert deals["walmart"][0]["store"] == "Walmart"
        mock_metro_scrape.assert_called_once()
        mock_walmart_scrape.assert_called_once()


def test_persist_deals(session: Session):
    # Arrange
    with patch('app.agents.scraper_agent.AsyncIOScheduler'):
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


@pytest.mark.asyncio
async def test_walmart_scraper_parsing_logic():
    """
    Tests the parsing logic of the WalmartScraper using mock HTML content.
    """
    # Arrange
    scraper = WalmartScraper()
    mock_page = AsyncMock()

    # Construct an absolute path to the mock HTML file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mock_html_path = os.path.join(current_dir, "mock_walmart_flyer.html")

    with open(mock_html_path, "r") as f:
        mock_html = f.read()

    # Mock the navigation call and set the content
    mock_page.goto = AsyncMock()
    mock_page.content = AsyncMock(return_value=mock_html)

    # Act
    deals = await scraper._scrape_page(mock_page, limit=10)

    # Assert
    assert len(deals) == 3
    assert deals[1]["name"] == "Wonder Bread"
    assert deals[1]["price"] == 2.50
    assert deals[2]["name"] == "Campbell's Soup"
    assert deals[2]["price"] == 1.25
    assert deals[0]["name"] == "Red Seedless Grapes"
    assert deals[0]["price"] == 2.97
    assert deals[0]["unit"] == "lb"

@pytest.mark.asyncio
async def test_provigo_scraper_parsing_logic():
    """
    Tests the parsing logic of the ProvigoScraper using mock HTML content.
    """
    # Arrange
    scraper = ProvigoScraper()
    mock_page = AsyncMock()
    mock_html = """
    <html>
        <body>
            <div class="product-tile-group__list__item">
                <h3 class="product-tile__name">PC Chicken Breasts</h3>
                <span class="price__value">12.99</span>
                <span class="product-tile__package-size">/kg</span>
                <img class="product-tile__image__image" src="http://example.com/image1.jpg"/>
            </div>
            <div class="product-tile-group__list__item">
                <h3 class="product-tile__name">Black Diamond Cheese</h3>
                <span class="price__value">2.49</span>
                <img class="product-tile__image__image" src="http://example.com/image2.jpg"/>
            </div>
        </body>
    </html>
    """
    # Mock the navigation and interaction calls to simulate a successful run
    mock_page.goto = AsyncMock()
    # Configure the locator to return a mock that can be clicked
    mock_locator = AsyncMock()
    mock_locator.click = AsyncMock()
    mock_page.locator.return_value = mock_locator
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.content = AsyncMock(return_value=mock_html)
    mock_page.evaluate = AsyncMock(return_value=1000)
    mock_page.wait_for_timeout = AsyncMock()

    # Act
    deals = await scraper._scrape_page(mock_page, limit=10)

    # Assert
    assert len(deals) == 2
    assert deals[0]["name"] == "PC Chicken Breasts"
    assert deals[0]["price"] == 12.99
    assert deals[0]["unit"] == "kg"
    assert deals[0]["image_url"] == "http://example.com/image1.jpg"
    assert deals[1]["name"] == "Black Diamond Cheese"
    assert deals[1]["price"] == 2.49
    assert deals[1]["unit"] == "each"
    assert deals[1]["image_url"] == "http://example.com/image2.jpg"

@pytest.mark.asyncio
async def test_iga_scraper_parsing_logic():
    """
    Tests the parsing logic of the IgaScraper using mock HTML content.
    """
    # Arrange
    scraper = IgaScraper()
    mock_page = AsyncMock()
    # Construct an absolute path to the mock HTML file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mock_html_path = os.path.join(current_dir, "mock_iga_flyer.html")
    with open(mock_html_path, "r") as f:
        mock_html = f.read()
    # Mock the navigation and interaction calls to simulate a successful run
    mock_page.goto = AsyncMock()
    # Configure the locator to return a mock that can be clicked
    mock_locator = AsyncMock()
    mock_locator.click = AsyncMock()
    mock_page.locator.return_value = mock_locator
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.content = AsyncMock(return_value=mock_html)
    # Act
    deals = await scraper._scrape_page(mock_page, limit=10)
    # Assert
    assert len(deals) == 2
    assert deals[0]["name"] == "Organic Bananas"
    assert deals[0]["price"] == 1.99
    assert deals[0]["unit"] == "lb"
    assert deals[1]["name"] == "Compliments Large Eggs"
    assert deals[1]["price"] == 3.49
    assert deals[1]["unit"] == "each"


@pytest.mark.asyncio
async def test_metro_scraper_parsing_logic():
    """
    Tests the parsing logic of the MetroScraper using mock HTML content.
    """
    # Arrange
    scraper = MetroScraper()
    mock_page = AsyncMock()
    mock_html = """
    <html>
        <body>
            <div class="product-tile-group__list__item">
                <h3 class="product-tile__name">Irresistibles Pastries</h3>
                <span class="price__value">3.99</span>
                <img class="product-tile__image__image" src="http://example.com/image1.jpg"/>
            </div>
            <div class="product-tile-group__list__item">
                <h3 class="product-tile__name">Red Grill Rib Steak</h3>
                <span class="price__value">8.88</span>
                <span class="product-tile__package-size">/lb</span>
                <img class="product-tile__image__image" src="http://example.com/image2.jpg"/>
            </div>
        </body>
    </html>
    """
    # Mock the navigation and interaction calls to simulate a successful run
    mock_page.goto = AsyncMock()
    # Configure the locator to return a mock that can be clicked
    mock_locator = AsyncMock()
    mock_locator.click = AsyncMock()
    mock_page.locator.return_value = mock_locator
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.content = AsyncMock(return_value=mock_html)
    # Act
    deals = await scraper._scrape_page(mock_page, limit=10)
    # Assert
    assert len(deals) == 2
    assert deals[0]["name"] == "Irresistibles Pastries"
    assert deals[0]["price"] == 3.99
    assert deals[0]["unit"] == "each"
    assert deals[0]["image_url"] == "http://example.com/image1.jpg"
    assert deals[1]["name"] == "Red Grill Rib Steak"
    assert deals[1]["price"] == 8.88
    assert deals[1]["unit"] == "lb"
    assert deals[1]["image_url"] == "http://example.com/image2.jpg"
