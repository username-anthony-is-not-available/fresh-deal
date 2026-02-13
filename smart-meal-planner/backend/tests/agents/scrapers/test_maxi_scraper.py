
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from bs4 import BeautifulSoup
from app.agents.scrapers.maxi_scraper import MaxiScraper

@pytest.mark.asyncio
async def test_parse_tile_flipp():
    scraper = MaxiScraper(headless=True)
    html = """
    <div data-testid="product-tile">
        <div data-testid="product-title">Chicken Breast</div>
        <div class="price__value">$5.99</div>
        <div class="product-tile__package-size">1 kg</div>
        <img src="https://example.com/chicken.jpg">
    </div>
    """
    soup = BeautifulSoup(html, 'html.parser')
    tile = soup.find('div', {'data-testid': 'product-tile'})

    deal = scraper._parse_tile(tile)

    assert deal['name'] == "Chicken Breast"
    assert deal['price'] == 5.99
    assert deal['unit'] == "kg"
    assert deal['image_url'] == "https://example.com/chicken.jpg"
    assert deal['store'] == "Maxi"

@pytest.mark.asyncio
async def test_parse_tile_native():
    scraper = MaxiScraper(headless=True)
    html = """
    <div class="product-tile">
        <h3 class="product-tile__name">Bacon</h3>
        <span class="price__value">$7.99</span>
        <span class="product-tile__package-size">500 g</span>
        <img src="https://example.com/bacon.jpg">
    </div>
    """
    soup = BeautifulSoup(html, 'html.parser')
    tile = soup.find('div', {'class': 'product-tile'})

    deal = scraper._parse_tile(tile)

    assert deal['name'] == "Bacon"
    assert deal['price'] == 7.99
    assert deal['unit'] == "each"
    assert deal['image_url'] == "https://example.com/bacon.jpg"

@pytest.mark.asyncio
async def test_parse_tile_multi_buy():
    scraper = MaxiScraper(headless=True)
    html = """
    <div data-testid="product-tile">
        <div data-testid="product-title">Yogurt</div>
        <div class="price__value">2/$5.00</div>
    </div>
    """
    soup = BeautifulSoup(html, 'html.parser')
    tile = soup.find('div', {'data-testid': 'product-tile'})

    deal = scraper._parse_tile(tile)

    assert deal['name'] == "Yogurt"
    assert deal['price'] == 2.50

@pytest.mark.asyncio
async def test_scrape_page_success():
    scraper = MaxiScraper(headless=True)
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.content = AsyncMock(return_value='<div class="product-tile"><h3 class="product-tile__name">Apple</h3><span class="price__value">$1.99</span></div>')
    mock_page.wait_for_selector = AsyncMock()
    mock_page.is_visible = AsyncMock(return_value=False)

    # Mock frame locator
    mock_frame = MagicMock()
    mock_frame.locator = MagicMock()
    mock_frame.locator().count = AsyncMock(return_value=0)
    mock_page.frame_locator = MagicMock(return_value=mock_frame)

    deals = await scraper._scrape_page(mock_page, limit=1)

    assert len(deals) == 1
    assert deals[0]['name'] == "Apple"
    assert deals[0]['price'] == 1.99

@pytest.mark.asyncio
async def test_scrape_page_flipp_iframe():
    scraper = MaxiScraper(headless=True)
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.is_visible = AsyncMock(return_value=False)

    # Mock frame locator
    mock_frame = MagicMock()
    mock_frame.locator = MagicMock()
    # Mock count to be > 0 so it uses the frame
    mock_frame.locator('div[data-testid="product-tile"]').count = AsyncMock(return_value=1)
    mock_frame.locator('html').inner_html = AsyncMock(return_value="""
        <div data-testid="product-tile">
            <div data-testid="product-title">Banana</div>
            <div class="price__value">$0.79</div>
        </div>
    """)
    mock_page.frame_locator = MagicMock(return_value=mock_frame)

    deals = await scraper._scrape_page(mock_page, limit=10)

    assert len(deals) == 1
    assert deals[0]['name'] == "Banana"
    assert deals[0]['price'] == 0.79
