import pytest
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from playwright.async_api import Page
from bs4 import BeautifulSoup

from app.agents.scrapers.walmart_scraper import WalmartScraper
from app.agents.scrapers.iga_scraper import IgaScraper
from app.agents.scrapers.metro_scraper import MetroScraper
from app.agents.scrapers.maxi_scraper import MaxiScraper
from app.agents.scrapers.provigo_scraper import ProvigoScraper
from app.agents.scrapers.super_c_scraper import SuperCScraper
from app.agents.scrapers.costco_scraper import CostcoScraper
from app.agents.scrapers.base_scraper import BaseScraper

# Constants for paths
SNAPSHOTS_DIR = os.path.join(os.path.dirname(__file__), "e2e", "snapshots")
MOCKS_DIR = os.path.dirname(__file__)

def get_snapshot_content(filename):
    path = os.path.join(SNAPSHOTS_DIR, filename)
    if not os.path.exists(path):
        path = os.path.join(MOCKS_DIR, filename)

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
async def test_walmart_regression():
    content = get_snapshot_content("mock_walmart_flyer.html")
    page = await mock_page_with_content(content)

    scraper = WalmartScraper()
    # Mocking external calls to avoid side effects
    scraper._handle_postal_code_modal = AsyncMock()
    scraper._scroll_to_bottom = AsyncMock()

    deals = await scraper._scrape_page(page, limit=10)

    assert len(deals) == 3
    assert any(d["name"] == "Red Seedless Grapes" and d["price"] == 2.97 for d in deals)
    assert any(d["name"] == "Wonder Bread" and d["price"] == 2.50 for d in deals)
    assert any(d["name"] == "Campbell's Soup" and d["price"] == 1.25 for d in deals)

@pytest.mark.asyncio
async def test_iga_regression():
    content = get_snapshot_content("mock_iga_flyer.html")
    # IGA _scrape_page expects the Flipp content to be in an iframe
    # and if not found, falls back to native content.
    # In mock_iga_flyer.html, the structure is Flipp-like but it's the main content.
    page = await mock_page_with_content(content)

    scraper = IgaScraper()
    # Mocking external calls
    scraper._handle_cookie_consent = AsyncMock()
    scraper._check_incapsula_block = AsyncMock(return_value=False)
    scraper._scroll_to_bottom = AsyncMock()

    # We want to test the full _scrape_page logic.
    # BaseScraper._scrape_flipp_frame will use our mocked frame_locator.
    deals = await scraper._scrape_page(page, limit=10)

    assert len(deals) == 2
    assert any(d["name"] == "Organic Bananas" and d["price"] == 1.99 for d in deals)
    assert any(d["name"] == "Compliments Large Eggs" and d["price"] == 3.49 for d in deals)

@pytest.mark.asyncio
async def test_metro_regression():
    content = get_snapshot_content("metro_native.html")
    page = await mock_page_with_content(content)

    scraper = MetroScraper()
    scraper._handle_cookie_consent = AsyncMock()
    scraper._check_incapsula_block = AsyncMock(return_value=False)
    scraper._scroll_to_bottom = AsyncMock()

    deals = await scraper._scrape_page(page, limit=10)

    assert len(deals) == 2
    assert any("Strawberries" in d["name"] and d["price"] == 4.99 for d in deals)
    assert any("Apples" in d["name"] and d["price"] == 1.49 for d in deals)

@pytest.mark.asyncio
async def test_maxi_regression():
    content = get_snapshot_content("mock_maxi_flyer.html")
    page = await mock_page_with_content(content)

    scraper = MaxiScraper()
    scraper._handle_cookie_consent = AsyncMock()
    scraper._check_incapsula_block = AsyncMock(return_value=False)
    scraper._handle_location = AsyncMock()
    scraper._scroll_to_bottom = AsyncMock()

    # Maxi uses both Flipp and native. In mock_maxi_flyer.html it's native.
    deals = await scraper._scrape_page(page, limit=10)

    assert len(deals) >= 1
    assert any("Chicken Breast" in d["name"] and d["price"] == 12.99 for d in deals)

@pytest.mark.asyncio
async def test_provigo_regression():
    content = get_snapshot_content("mock_provigo_flyer.html")
    page = await mock_page_with_content(content)

    scraper = ProvigoScraper()
    scraper._handle_cookie_consent = AsyncMock()
    scraper._check_incapsula_block = AsyncMock(return_value=False)
    scraper._scroll_to_bottom = AsyncMock()

    # Provigo uses both Flipp and native.
    deals = await scraper._scrape_page(page, limit=10)

    assert len(deals) >= 1
    assert any("Chicken Breasts" in d["name"] and d["price"] == 12.99 for d in deals)

@pytest.mark.asyncio
async def test_super_c_regression():
    content = get_snapshot_content("superc_iframe.html")
    page = await mock_page_with_content(content)

    scraper = SuperCScraper()
    scraper._handle_cookie_consent = AsyncMock()
    scraper._check_incapsula_block = AsyncMock(return_value=False)
    scraper._scroll_to_bottom = AsyncMock()

    deals = await scraper._scrape_page(page, limit=10)

    assert len(deals) == 2
    assert any("Bananas" in d["name"] and d["price"] == 1.99 for d in deals)

@pytest.mark.asyncio
async def test_costco_regression():
    content = get_snapshot_content("costco_native.html")
    page = await mock_page_with_content(content)

    scraper = CostcoScraper()
    scraper._handle_cookie_consent = AsyncMock()
    scraper._check_incapsula_block = AsyncMock(return_value=False)
    scraper._scroll_to_bottom = AsyncMock()

    # Mocking the next button check
    page.query_selector = AsyncMock(return_value=None)

    deals = await scraper._scrape_page(page, limit=10)

    assert len(deals) == 2
    assert any("Olive Oil" in d["name"] and d["price"] == 24.99 for d in deals)
    assert any("Bounty" in d["name"] and d["price"] == 29.99 for d in deals)
