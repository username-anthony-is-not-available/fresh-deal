import pytest
import os
import asyncio
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
