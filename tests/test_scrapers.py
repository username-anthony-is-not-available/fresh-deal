import pytest
import os
from unittest.mock import AsyncMock, MagicMock
from playwright.async_api import Page

from src.scrapers.metro_scraper import MetroScraper
from src.scrapers.super_c_scraper import SuperCScraper
from src.scrapers.provigo_scraper import ProvigoScraper

# Constants for paths
SNAPSHOTS_DIR = os.path.join(os.path.dirname(__file__), "snapshots")

def get_snapshot_content(filename):
    path = os.path.join(SNAPSHOTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

async def mock_page_with_content(content):
    mock_page = MagicMock(spec=Page)
    mock_page.goto = AsyncMock()
    mock_page.content = AsyncMock(return_value=content)
    mock_page.wait_for_selector = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value=0)
    mock_page.screenshot = AsyncMock()
    mock_page.is_visible = AsyncMock(return_value=False)
    mock_page.url = "https://example.com"
    mock_page.viewport_size = {"width": 1280, "height": 720}
    mock_page.mouse = MagicMock()
    mock_page.mouse.move = AsyncMock()

    # For Flipp iframe scrapers
    mock_frame_locator = MagicMock()
    mock_page.frame_locator.return_value = mock_frame_locator

    mock_html_locator = MagicMock()
    mock_html_locator.inner_html = AsyncMock(return_value=content)

    mock_tile_locator = MagicMock()
    mock_tile_locator.first = MagicMock()
    mock_tile_locator.first.wait_for = AsyncMock()

    def locator_side_effect(selector):
        if selector == 'html':
            return mock_html_locator
        return mock_tile_locator

    mock_frame_locator.locator.side_effect = locator_side_effect

    return mock_page

@pytest.mark.asyncio
async def test_metro_parsing():
    content = get_snapshot_content("metro_native.html")
    scraper = MetroScraper()
    deals = scraper.parse_html(content)

    assert len(deals) >= 2
    assert any("Strawberries" in d.name and d.price == 4.99 for d in deals)
    assert any("Apples" in d.name and d.price == 1.49 for d in deals)

@pytest.mark.asyncio
async def test_super_c_parsing():
    # Super C iframe snapshot
    content = get_snapshot_content("superc_iframe.html")
    page = await mock_page_with_content(content)

    scraper = SuperCScraper()
    # Mock _scrape_flipp_frame to return the tiles from BeautifulSoup
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(content, 'html.parser')
    tiles = soup.select('div[data-testid="product-tile"]')

    scraper._scrape_flipp_frame = AsyncMock(return_value=tiles)
    scraper._check_incapsula_block = AsyncMock(return_value=False)
    scraper._handle_cookie_consent = AsyncMock(return_value=True)
    scraper._random_delay = AsyncMock()

    deals = await scraper.fetch_deals(page, limit=10)

    assert len(deals) == 2
    assert any("Bananas" in d.name and d.price == 1.99 for d in deals)

@pytest.mark.asyncio
async def test_provigo_parsing():
    # Verify we didn't break existing stuff
    content = get_snapshot_content("provigo_iframe.html")
    scraper = ProvigoScraper()
    deals = scraper.parse_html(content)
    assert isinstance(deals, list)
    assert len(deals) >= 2
    assert any("Bananas" in d.name and d.price == 1.99 for d in deals)

@pytest.mark.asyncio
async def test_metro_parsing_missing_brand():
    content = """
    <div class="default-product-tile tile-product">
        <span class="head__title">No Brand Item</span>
        <div class="pricing__sale-price">
            <span class="price-update">$2.99</span>
        </div>
    </div>
    """
    scraper = MetroScraper()
    deals = scraper.parse_html(content)
    assert len(deals) == 1
    assert deals[0].name == "No Brand Item"
    assert deals[0].price == 2.99

@pytest.mark.asyncio
async def test_super_c_native_fallback():
    # Super C native tiles snapshot (we'll reuse metro-like content to simulate native tiles)
    content = """
    <div class="product-tile">
        <h3 class="product-tile__name">Native Super C Item</h3>
        <span class="price__value">$3.99</span>
    </div>
    """
    page = await mock_page_with_content(content)
    scraper = SuperCScraper()

    # Mock _scrape_flipp_frame to return empty list
    scraper._scrape_flipp_frame = AsyncMock(return_value=[])
    scraper._check_incapsula_block = AsyncMock(return_value=False)
    scraper._handle_cookie_consent = AsyncMock(return_value=True)
    scraper._random_delay = AsyncMock()

    deals = await scraper.fetch_deals(page, limit=10)
    assert len(deals) == 1
    assert deals[0].name == "Native Super C Item"
    assert deals[0].price == 3.99

@pytest.mark.asyncio
async def test_base_scraper_bot_block():
    scraper = MetroScraper()

    # We need to mock the context/page creation to return our mock page
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_page = await mock_page_with_content("Incapsula incident ID")

    scraper._get_browser = AsyncMock(return_value=mock_browser)
    scraper._get_context = AsyncMock(return_value=mock_context)
    scraper._get_page = AsyncMock(return_value=mock_page)
    scraper._save_debug_artifacts = AsyncMock(return_value=("s.png", "h.html"))

    # We don't actually want to run async_playwright, so we mock it in the scraper.scrape method context
    # But it's easier to just test _check_incapsula_block directly and then the logic in scrape if possible

    with pytest.raises(Exception) as excinfo:
        await scraper.scrape()
    assert "[BOT_BLOCK]" in str(excinfo.value)

@pytest.mark.asyncio
async def test_metro_fetch_deals_success():
    scraper = MetroScraper()
    mock_page = await mock_page_with_content(get_snapshot_content("metro_native.html"))
    # Mock some methods to avoid long delays and external calls
    scraper._handle_cookie_consent = AsyncMock()
    scraper._scroll_to_bottom = AsyncMock()
    scraper._check_incapsula_block = AsyncMock(return_value=False)

    deals = await scraper.fetch_deals(mock_page, limit=5)
    assert len(deals) > 0

@pytest.mark.asyncio
async def test_provigo_fetch_deals_success():
    scraper = ProvigoScraper()
    mock_page = await mock_page_with_content(get_snapshot_content("provigo_iframe.html"))
    scraper._handle_cookie_consent = AsyncMock()
    scraper._scroll_to_bottom = AsyncMock()

    deals = await scraper.fetch_deals(mock_page, limit=5)
    assert len(deals) > 0

@pytest.mark.asyncio
async def test_base_scraper_utils_coverage():
    scraper = MetroScraper()
    # Test _type_with_random_delay
    mock_page = MagicMock(spec=Page)
    mock_page.type = AsyncMock()
    scraper._random_delay = AsyncMock()
    await scraper._type_with_random_delay(mock_page, "selector", "abc")
    assert mock_page.type.call_count == 3

    # Test _handle_cookie_consent
    mock_page.is_visible = AsyncMock(return_value=True)
    mock_page.locator = MagicMock()
    mock_page.locator().click = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()
    await scraper._handle_cookie_consent(mock_page, "selector")

    # Test _scroll_to_bottom
    # scrollHeight initial, then scrollHeight after each scroll (max_scrolls=2)
    mock_page.evaluate = AsyncMock(side_effect=[100, 200, 200, 200, 200])
    await scraper._scroll_to_bottom(mock_page, max_scrolls=2)

    # Test _scrape_flipp_frame
    mock_page.wait_for_selector = AsyncMock()
    # flyer_frame.locator('html').inner_html()
    mock_page.frame_locator().locator().inner_html = AsyncMock(return_value='<div data-testid="product-tile">Iframe Item</div>')
    # flyer_frame.locator(tile_selector).first.wait_for()
    mock_page.frame_locator().locator().first.wait_for = AsyncMock()

    tiles = await scraper._scrape_flipp_frame(mock_page)
    assert len(tiles) == 1
    assert "Iframe Item" in tiles[0].get_text()

@pytest.mark.asyncio
async def test_base_scraper_save_debug_artifacts():
    scraper = MetroScraper()
    mock_page = MagicMock(spec=Page)
    mock_page.screenshot = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html></html>")

    # Actually it's easier to just let it write and check the return value
    s_path, h_path = await scraper._save_debug_artifacts(mock_page, "test")
    assert "/tmp/scrapers/test_" in s_path
    assert "/tmp/scrapers/test_" in h_path
    assert s_path.endswith(".png")
    assert h_path.endswith(".html")

@pytest.mark.asyncio
async def test_base_scraper_get_browser_context_page():
    # Test _get_browser, _get_context, _get_page
    scraper = MetroScraper()
    # Mock playwright
    mock_p = MagicMock()
    mock_p.chromium.launch = AsyncMock()
    await scraper._get_browser(mock_p, proxy="http://proxy.com")
    mock_p.chromium.launch.assert_called_once()

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock()
    await scraper._get_context(mock_browser)
    mock_browser.new_context.assert_called_once()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock()
    await scraper._get_page(mock_context)
    mock_context.new_page.assert_called_once()

@pytest.mark.asyncio
async def test_metro_fetch_deals_error_handling():
    scraper = MetroScraper()
    mock_page = await mock_page_with_content("error")
    mock_page.goto = AsyncMock(side_effect=Exception("Connection error"))

    deals = await scraper.fetch_deals(mock_page, limit=5)
    assert deals == []

@pytest.mark.asyncio
async def test_super_c_fetch_deals_error_handling():
    scraper = SuperCScraper()
    mock_page = await mock_page_with_content("error")
    mock_page.goto = AsyncMock(side_effect=Exception("Connection error"))
    scraper._save_debug_artifacts = AsyncMock(return_value=("s.png", "h.html"))

    deals = await scraper.fetch_deals(mock_page, limit=5)
    assert deals == []
    scraper._save_debug_artifacts.assert_called_once()

@pytest.mark.asyncio
async def test_provigo_fetch_deals_spinner_timeout():
    scraper = ProvigoScraper()
    mock_page = await mock_page_with_content(get_snapshot_content("provigo_iframe.html"))
    # Trigger Exception in wait_for_selector
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))
    scraper._handle_cookie_consent = AsyncMock()
    scraper._scroll_to_bottom = AsyncMock()

    deals = await scraper.fetch_deals(mock_page, limit=5)
    assert len(deals) > 0

@pytest.mark.asyncio
async def test_metro_fetch_deals_bot_detected_in_loop():
    scraper = MetroScraper()
    mock_page = await mock_page_with_content("bot")
    scraper._check_incapsula_block = AsyncMock(return_value=True)
    scraper._handle_cookie_consent = AsyncMock()

    deals = await scraper.fetch_deals(mock_page, limit=5)
    assert deals == []

@pytest.mark.asyncio
async def test_metro_fetch_deals_scroll_error():
    scraper = MetroScraper()
    mock_page = await mock_page_with_content(get_snapshot_content("metro_native.html"))
    scraper._scroll_to_bottom = AsyncMock(side_effect=Exception("Scroll error"))
    scraper._check_incapsula_block = AsyncMock(return_value=False)
    scraper._handle_cookie_consent = AsyncMock()

    deals = await scraper.fetch_deals(mock_page, limit=5)
    assert len(deals) > 0

@pytest.mark.asyncio
async def test_base_scraper_flipp_frame_error():
    scraper = MetroScraper()
    mock_page = MagicMock(spec=Page)
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Frame timeout"))

    tiles = await scraper._scrape_flipp_frame(mock_page)
    assert tiles == []

@pytest.mark.asyncio
async def test_metro_parse_html_edge_cases():
    scraper = MetroScraper()
    # 1. Missing elements
    content = '<div class="default-product-tile tile-product"></div>'
    assert scraper.parse_html(content) == []

    # 2. Regular price element with $
    content = """
    <div class="default-product-tile tile-product">
        <span class="head__title">Item</span>
        <div class="pricing__sale-price"><span class="price-update">$5.00</span></div>
        <div class="pricing__before-price"><span>Regular $7.00</span></div>
    </div>
    """
    deals = scraper.parse_html(content)
    assert len(deals) == 1
    assert deals[0].original_price == 7.0

    # 3. Alternative product tiles
    content = """
    <div class="product-tile-group__list__item">
        <h3 class="product-tile__name">Alternative Item</h3>
        <span class="price__value">$3.00</span>
    </div>
    """
    deals = scraper.parse_html(content)
    assert len(deals) == 1
    assert deals[0].name == "Alternative Item"

@pytest.mark.asyncio
async def test_provigo_parse_html_edge_cases():
    scraper = ProvigoScraper()
    # 1. Product grid component
    content = """
    <div data-testid="product-grid-component">
        <h3 data-testid="product-title">Grid Item</h3>
        <div data-testid="price-product-tile">$4.00</div>
    </div>
    """
    deals = scraper.parse_html(content)
    assert len(deals) == 1
    assert deals[0].name == "Grid Item"

    # 2. Package size
    content = """
    <div data-testid="product-tile">
        <h3 data-testid="product-title">Item with Unit</h3>
        <div data-testid="price-product-tile">$4.00</div>
        <div data-testid="product-package-size">500 g</div>
    </div>
    """
    deals = scraper.parse_html(content)
    assert len(deals) == 1
    assert deals[0].unit == "g"

@pytest.mark.asyncio
async def test_super_c_parse_tile_edge_cases():
    scraper = SuperCScraper()
    # 1. Sale price data-testid
    from bs4 import BeautifulSoup
    content = """
    <div class="product-tile">
        <h3 class="product-tile__name">Super C Item</h3>
        <span data-testid="sale-price">$2.00</span>
    </div>
    """
    soup = BeautifulSoup(content, 'html.parser')
    deal = scraper._parse_tile(soup.find('div'))
    assert deal.price == 2.0

@pytest.mark.asyncio
async def test_super_c_fetch_deals_native_fallback_error():
    scraper = SuperCScraper()
    mock_page = await mock_page_with_content("<html><body>Native</body></html>")
    scraper._scrape_flipp_frame = AsyncMock(return_value=[])
    # Trigger Exception in wait_for_selector
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))
    scraper._handle_cookie_consent = AsyncMock()

    deals = await scraper.fetch_deals(mock_page, limit=5)
    assert deals == []

@pytest.mark.asyncio
async def test_provigo_fetch_deals_no_deals():
    scraper = ProvigoScraper()
    # Mock page with no deals to trigger artifacts saving
    mock_page = await mock_page_with_content("<html><body>No deals here</body></html>")
    scraper._handle_cookie_consent = AsyncMock()
    scraper._scroll_to_bottom = AsyncMock()
    scraper._save_debug_artifacts = AsyncMock(return_value=("s.png", "h.html"))

    deals = await scraper.fetch_deals(mock_page, limit=5)
    assert deals == []
    scraper._save_debug_artifacts.assert_called_once()

@pytest.mark.asyncio
async def test_metro_fetch_deals_no_deals():
    scraper = MetroScraper()
    # Mock page with no deals to trigger artifacts saving
    mock_page = await mock_page_with_content("<html><body>No deals here</body></html>")
    scraper._handle_cookie_consent = AsyncMock()
    scraper._scroll_to_bottom = AsyncMock()
    scraper._check_incapsula_block = AsyncMock(return_value=False)
    scraper._save_debug_artifacts = AsyncMock(return_value=("s.png", "h.html"))

    deals = await scraper.fetch_deals(mock_page, limit=5)
    assert deals == []
    scraper._save_debug_artifacts.assert_called_once()
