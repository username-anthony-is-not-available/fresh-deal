import pytest
import pytest_asyncio
from datetime import date, timedelta
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.agents.scraper_agent import ScraperAgent
from app.models.all_models import Store, Product, Deal
import asyncio
from playwright.async_api import Page
from bs4 import BeautifulSoup
from unittest.mock import AsyncMock, patch, MagicMock
from app.agents.scrapers.walmart_scraper import WalmartScraper
from app.agents.scrapers.provigo_scraper import ProvigoScraper
from app.agents.scrapers.iga_scraper import IgaScraper
from app.agents.scrapers.metro_scraper import MetroScraper
from app.agents.scrapers.maxi_scraper import MaxiScraper
from app.agents.scrapers.super_c_scraper import SuperCScraper
from app.agents.scrapers.base_scraper import BaseScraper
import os

# In-memory SQLite database for testing
engine = create_engine("sqlite:///:memory:")
async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")

def setup_database():
    SQLModel.metadata.create_all(engine)

async def setup_async_database():
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

def teardown_database():
    SQLModel.metadata.drop_all(engine)

async def teardown_async_database():
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

@pytest.fixture(name="session")
def session_fixture():
    setup_database()
    with Session(engine) as session:
        yield session
    teardown_database()

@pytest_asyncio.fixture
async def async_session():
    await setup_async_database()
    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        yield session
    await teardown_async_database()

@pytest.mark.asyncio
async def test_scraper_agent_orchestration_with_mocked_scrapers(async_session: AsyncSession):
    # Arrange
    agent = ScraperAgent(async_session)
    stores = ["metro", "maxi"]

    # Mock the scrape methods of the individual direct scrapers
    with patch('app.agents.scrapers.metro_scraper.MetroScraper.scrape', new_callable=AsyncMock) as mock_metro_scrape, \
         patch('app.agents.scrapers.maxi_scraper.MaxiScraper.scrape', new_callable=AsyncMock) as mock_maxi_scrape:

        mock_metro_scrape.return_value = [{"name": "Metro Product", "price": 1.0, "store": "Metro"}]
        mock_maxi_scrape.return_value = [{"name": "Maxi Product", "price": 2.0, "store": "Maxi"}]

        # Act
        deals = await agent.scrape(stores)

        # Assert
        assert len(deals) == 2
        assert "metro" in deals
        assert "maxi" in deals
        assert deals["metro"][0]["store"] == "Metro"
        assert deals["maxi"][0]["store"] == "Maxi"
        mock_metro_scrape.assert_called_once()
        mock_maxi_scrape.assert_called_once()


@pytest.mark.asyncio
async def test_persist_deals_duplicate_prevention(async_session: AsyncSession):
    # Arrange
    agent = ScraperAgent(async_session)
    valid_until = date.today() + timedelta(days=7)
    deals_to_persist = [
        {"name": "Unique Product", "price": 5.0, "store": "Store A", "category": "Cat", "unit": "each", "valid_until": valid_until},
    ]

    # Act - Persist once
    await agent.persist_deals(deals_to_persist)

    # Act - Persist again (should be skipped)
    await agent.persist_deals(deals_to_persist)

    # Assert
    result = await async_session.execute(select(Deal))
    deals = result.scalars().all()
    assert len(deals) == 1


@pytest.mark.asyncio
async def test_scraper_agent_concurrency(async_session: AsyncSession):
    """
    Tests that the ScraperAgent scrapes multiple stores concurrently.
    """
    # Arrange
    agent = ScraperAgent(async_session)
    stores = ["metro", "walmart", "maxi"]

    # Mock _scrape_store to measure timing
    async def mock_scrape_store(store_name, limit):
        await asyncio.sleep(0.5)  # Simulate some work
        return [{"name": f"{store_name} Product", "price": 1.0, "store": store_name}]

    with patch.object(
        agent, "_scrape_store", side_effect=mock_scrape_store
    ) as mock_scrape:
        start_time = asyncio.get_event_loop().time()

        # Act
        deals = await agent.scrape(stores)

        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time

        # Assert
        assert len(deals) == 3
        # If sequential, duration would be >= 1.5s
        # If concurrent, duration should be around 0.5s - 0.8s
        assert duration < 1.2
        assert mock_scrape.call_count == 3


@pytest.mark.asyncio
async def test_persist_deals(async_session: AsyncSession):
    # Arrange
    agent = ScraperAgent(async_session)
    deals_to_persist = [
        {"name": "Test Product 1", "price": 1.99, "original_price": 2.99, "store": "Test Store", "category": "Test Category", "unit": "each"},
        {"name": "Test Product 2", "price": 0.99, "store": "Test Store", "category": "Test Category", "unit": "kg"},
    ]

    # Act
    await agent.persist_deals(deals_to_persist)

    # Assert
    result = await async_session.execute(select(Deal))
    deals = result.scalars().all()
    result = await async_session.execute(select(Product))
    products = result.scalars().all()
    result = await async_session.execute(select(Store))
    stores = result.scalars().all()

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
    Tests the parsing logic of the ProvigoScraper using mock HTML content from file.
    Tests the Flipp iframe handling logic.
    """
    # Arrange
    scraper = ProvigoScraper()
    mock_page = MagicMock(spec=Page)

    # Construct an absolute path to the mock HTML file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mock_html_path = os.path.join(current_dir, "mock_provigo_flyer.html")

    with open(mock_html_path, "r") as f:
        mock_html = f.read()

    # Mock the navigation and interaction calls
    mock_page.goto = AsyncMock()
    mock_page.is_visible = AsyncMock(return_value=False)
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html></html>")
    mock_page.screenshot = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()

    # Mock frame_locator for Flipp iframe
    mock_frame_locator = MagicMock()
    mock_page.frame_locator.return_value = mock_frame_locator

    mock_tile_locator = MagicMock()
    mock_tile_locator.first = MagicMock()
    mock_tile_locator.first.wait_for = AsyncMock()

    mock_html_locator = MagicMock()
    mock_html_locator.inner_html = AsyncMock(return_value=mock_html)

    def locator_side_effect(selector):
        if selector == 'html':
            return mock_html_locator
        return mock_tile_locator

    mock_frame_locator.locator.side_effect = locator_side_effect

    # Act
    deals = await scraper._scrape_page(mock_page, limit=10)

    # Assert
    assert len(deals) == 2
    assert "Chicken Breasts" in deals[0]["name"]
    assert deals[0]["price"] == 12.99
    assert deals[0]["unit"] == "kg"
    assert deals[1]["name"] == "Black Diamond Cheese Slices"
    assert deals[1]["price"] == 2.49
    assert deals[1]["unit"] == "each"

@pytest.mark.asyncio
async def test_iga_scraper_parsing_logic():
    """
    Tests the parsing logic of the IgaScraper using mock HTML content from file.
    """
    # Arrange
    scraper = IgaScraper()
    mock_page = MagicMock(spec=Page)

    # Construct an absolute path to the mock HTML file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mock_html_path = os.path.join(current_dir, "mock_iga_flyer.html")
    with open(mock_html_path, "r") as f:
        mock_html = f.read()

    # Mock the navigation and interaction calls
    mock_page.goto = AsyncMock()
    mock_page.is_visible = AsyncMock(return_value=False)
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.content = AsyncMock(return_value=mock_html)
    mock_page.evaluate = AsyncMock(return_value=1000)
    mock_page.screenshot = AsyncMock()

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
    mock_page = MagicMock(spec=Page)
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
    mock_page.is_visible = AsyncMock(return_value=False)
    # Configure the locator to return a mock that can be clicked
    mock_locator = MagicMock()
    mock_locator.click = AsyncMock()
    mock_page.locator.return_value = mock_locator
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.content = AsyncMock(return_value=mock_html)
    mock_page.evaluate = AsyncMock(side_effect=[1000, 1000, 1000]) # For scroll logic

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

@pytest.mark.asyncio
async def test_maxi_scraper_parsing_logic():
    """
    Tests the parsing logic of the MaxiScraper using mock HTML content.
    """
    # Arrange
    scraper = MaxiScraper()
    mock_page = MagicMock(spec=Page)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    mock_html_path = os.path.join(current_dir, "mock_maxi_flyer.html")
    with open(mock_html_path, "r") as f:
        mock_html = f.read()

    mock_page.goto = AsyncMock()
    mock_page.is_visible = AsyncMock(return_value=True) # for cookie/location
    mock_page.click = AsyncMock()
    mock_page.fill = AsyncMock()
    mock_page.keyboard = MagicMock()
    mock_page.keyboard.press = AsyncMock()
    mock_page.content = AsyncMock(return_value=mock_html)
    mock_page.evaluate = AsyncMock(return_value=1000)

    # Mock Flipp frame
    mock_frame_locator = MagicMock()
    mock_page.frame_locator.return_value = mock_frame_locator
    mock_frame_locator.locator.return_value.count = AsyncMock(return_value=0)

    # Act
    deals = await scraper._scrape_page(mock_page, limit=10)

    # Assert
    assert len(deals) == 3
    assert deals[0]["name"] == "PC Blue Menu Chicken Breast"
    assert deals[0]["price"] == 12.99
    assert deals[0]["unit"] == "kg"
    assert deals[0]["category"] == "Meat & Poultry"

    assert deals[1]["name"] == "Grapes"
    assert deals[1]["price"] == 2.50
    assert deals[1]["category"] == "Fruits"

    assert deals[2]["name"] == "Apples"
    assert deals[2]["price"] == 3.99
    assert deals[2]["original_price"] == 4.99
    assert deals[2]["unit"] == "lb"
    assert deals[2]["category"] == "Fruits"

def test_base_scraper_utilities():
    """
    Tests the utility methods in BaseScraper.
    """
    class TestScraper(BaseScraper):
        async def _scrape_page(self, page, limit): return []

    scraper = TestScraper()

    # Test _parse_price
    assert scraper._parse_price("$3.99") == 3.99
    assert scraper._parse_price("2 for $5.00") == 2.50
    assert scraper._parse_price("2/$6.00") == 3.00
    assert scraper._parse_price("2 pour 7,00$") == 3.50
    assert scraper._parse_price("4.50") == 4.50

    # Test _extract_unit
    assert scraper._extract_unit("Chicken Breast 1kg") == "kg"
    assert scraper._extract_unit("Apples per lb") == "lb"
    assert scraper._extract_unit("Milk 2L") == "L"
    assert scraper._extract_unit("Eggs 12pk") == "each"

    # Test _categorize_product
    assert scraper._categorize_product("Chicken Thighs") == "Meat & Poultry"
    assert scraper._categorize_product("Salmon Fillet") == "Seafood"
    assert scraper._categorize_product("Bananas") == "Fruits"
    assert scraper._categorize_product("Broccoli") == "Vegetables"
    assert scraper._categorize_product("Cheddar Cheese") == "Dairy & Eggs"
    assert scraper._categorize_product("Whole Wheat Bread") == "Bakery"
    assert scraper._categorize_product("Orange Juice") == "Beverages"
    assert scraper._categorize_product("Basmati Rice") == "Pantry"
    assert scraper._categorize_product("Frozen Pizza") == "Frozen"
    assert scraper._categorize_product("Potato Chips") == "Snacks"
    assert scraper._categorize_product("Unknown Item 123") == "Grocery"

    # Test _parse_discount
    assert scraper._parse_discount("Save 20%") == 20.0
    assert scraper._parse_discount("30% off") == 30.0

    # Test _calculate_original_price
    assert scraper._calculate_original_price(8.0, 20.0) == 10.0
    assert scraper._calculate_original_price(5.0, None) == 5.0

    # Test _parse_flyer_dates (English)
    s, e = scraper._parse_flyer_dates("from Jan 30 to Feb 5, 2024")
    assert s == date(2024, 1, 30)
    assert e == date(2024, 2, 5)

    # Test _parse_flyer_dates (French)
    s, e = scraper._parse_flyer_dates("du 30 janv. au 5 févr. 2024")
    assert s == date(2024, 1, 30)
    assert e == date(2024, 2, 5)

    # Test _parse_flyer_dates (Single month French)
    s, e = scraper._parse_flyer_dates("du 25 au 31 juillet 2024")
    assert s == date(2024, 7, 25)
    assert e == date(2024, 7, 31)

@pytest.mark.asyncio
async def test_super_c_scraper_parsing_logic():
    """
    Tests the parsing logic of the SuperCScraper using mock HTML content.
    """
    # Arrange
    scraper = SuperCScraper()
    mock_page = MagicMock(spec=Page)

    # Super C uses the same Flipp format as Provigo in our mock data
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mock_html_path = os.path.join(current_dir, "mock_provigo_flyer.html")
    with open(mock_html_path, "r") as f:
        mock_html = f.read()

    mock_page.goto = AsyncMock()
    mock_page.is_visible = AsyncMock(return_value=False)
    mock_page.content = AsyncMock(return_value="<html></html>")
    mock_page.wait_for_selector = AsyncMock()

    # Mock centralized Flipp frame scraper (it's a method of BaseScraper)
    # Since SuperCScraper inherits from BaseScraper, we can mock the method on the instance or class
    with patch.object(BaseScraper, '_scrape_flipp_frame', new_callable=AsyncMock) as mock_flipp:
        # The mock flipp frame should return a list of BeautifulSoup objects (tiles)
        soup = BeautifulSoup(mock_html, 'html.parser')
        mock_flipp.return_value = soup.select('div[data-testid="product-tile"]')

        # Act
        deals = await scraper._scrape_page(mock_page, limit=10)

        # Assert
        assert len(deals) == 2
        assert "Chicken Breasts" in deals[0]["name"]
        assert deals[0]["price"] == 12.99
        assert deals[0]["store"] == "Super C"
        assert deals[1]["name"] == "Black Diamond Cheese Slices"
        assert deals[1]["price"] == 2.49
