import pytest
from unittest.mock import AsyncMock, MagicMock
from playwright.async_api import Page
from app.agents.scrapers.provigo_scraper import ProvigoScraper
import os
from bs4 import BeautifulSoup

@pytest.mark.asyncio
async def test_provigo_scraper_parsing_logic():
    """
    Tests the parsing logic of the ProvigoScraper using mock HTML content.
    """
    scraper = ProvigoScraper()
    mock_page = MagicMock(spec=Page)

    # Load mock HTML
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mock_html_path = os.path.join(current_dir, "../../mock_provigo_flyer.html")
    with open(mock_html_path, "r") as f:
        mock_html = f.read()

    # Mock page methods
    mock_page.goto = AsyncMock()
    mock_page.is_visible = AsyncMock(return_value=False)
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html></html>")

    # Mock frame locator for Flipp iframe
    mock_frame = MagicMock()
    mock_page.frame_locator.return_value = mock_frame

    mock_tile_locator = MagicMock()
    mock_tile_locator.first.wait_for = AsyncMock()

    mock_html_locator = MagicMock()
    mock_html_locator.inner_html = AsyncMock(return_value=mock_html)

    def locator_side_effect(selector):
        if selector == 'html':
            return mock_html_locator
        return mock_tile_locator

    mock_frame.locator.side_effect = locator_side_effect

    # Act
    deals = await scraper._scrape_page(mock_page, limit=10)

    # Assert
    assert len(deals) >= 2
    assert any("Chicken Breasts" in d["name"] and d["price"] == 12.99 for d in deals)
    assert any(d["name"] == "Black Diamond Cheese Slices" and d["price"] == 2.49 for d in deals)

@pytest.mark.asyncio
async def test_provigo_multi_buy_parsing():
    """
    Tests the multi-buy price parsing logic in ProvigoScraper.
    """
    scraper = ProvigoScraper()

    # Mock BeautifulSoup tile for "2 for $5.00"
    html_2_for_5 = '<div data-testid="product-tile"><div data-testid="product-title">Chips</div><div class="price__value">2 for $5.00</div></div>'
    soup_2_for_5 = BeautifulSoup(html_2_for_5, 'html.parser')
    deal_2_for_5 = scraper._parse_tile(soup_2_for_5)
    assert deal_2_for_5["price"] == 2.50

    # Mock BeautifulSoup tile for "2/$6.00"
    html_2_slash_6 = '<div data-testid="product-tile"><div data-testid="product-title">Juice</div><div class="price__value">2/$6.00</div></div>'
    soup_2_slash_6 = BeautifulSoup(html_2_slash_6, 'html.parser')
    deal_2_slash_6 = scraper._parse_tile(soup_2_slash_6)
    assert deal_2_slash_6["price"] == 3.00

@pytest.mark.asyncio
async def test_scrape_handles_timeout_gracefully():
    """Returns an empty list when Provigo product tiles never appear."""
    mock_page = AsyncMock(spec=Page)
    mock_page.goto = AsyncMock()
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))
    mock_page.content = AsyncMock(return_value="<html></html>")
    mock_page.screenshot = AsyncMock()

    scraper = ProvigoScraper(headless=True)
    deals = await scraper._scrape_page(mock_page, limit=10)
    assert deals == []
