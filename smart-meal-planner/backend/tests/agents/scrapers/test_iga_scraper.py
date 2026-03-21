import pytest
from unittest.mock import AsyncMock, MagicMock
from playwright.async_api import Page
from app.agents.scrapers.iga_scraper import IgaScraper
import os

@pytest.mark.asyncio
async def test_iga_scraper_parsing_logic():
    """
    Tests the parsing logic of the IgaScraper using mock HTML content.
    """
    scraper = IgaScraper()
    mock_page = MagicMock(spec=Page)

    # Load mock HTML
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Assuming the mock file is in the parent directory as seen in exploration
    mock_html_path = os.path.join(current_dir, "../../mock_iga_flyer.html")
    with open(mock_html_path, "r") as f:
        mock_html = f.read()

    # Mock page methods
    mock_page.goto = AsyncMock()
    mock_page.content = AsyncMock(return_value=mock_html)
    mock_page.wait_for_selector = AsyncMock()
    mock_page.is_visible = AsyncMock(return_value=False)
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value=1000)

    # Mock frame locator for Flipp fallback (should return empty initially to test main page parsing)
    mock_frame = MagicMock()
    mock_frame.locator.return_value.inner_html = AsyncMock(side_effect=Exception("No frame"))
    mock_page.frame_locator.return_value = mock_frame

    # Act
    deals = await scraper._scrape_page(mock_page, limit=10)

    # Assert
    assert len(deals) >= 2
    assert any(d["name"] == "Organic Bananas" and d["price"] == 1.99 for d in deals)
    assert any(d["name"] == "Compliments Large Eggs" and d["price"] == 3.49 for d in deals)

@pytest.mark.asyncio
async def test_iga_scraper_flipp_iframe_parsing():
    """
    Tests the Flipp iframe parsing logic for IGA.
    """
    scraper = IgaScraper()
    mock_page = MagicMock(spec=Page)

    # Mock Flipp HTML
    flipp_html = """
    <html>
        <body>
            <div data-testid="product-tile">
                <div data-testid="product-title">Flipp Chicken</div>
                <div class="price__value">$10.00</div>
                <div class="product-tile__package-size">kg</div>
            </div>
        </body>
    </html>
    """

    mock_page.goto = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html><body>Incapsula No</body></html>")
    mock_page.wait_for_selector = AsyncMock()
    mock_page.is_visible = AsyncMock(return_value=False)
    mock_page.evaluate = AsyncMock(return_value=1000)

    # Mock frame locator
    mock_frame = MagicMock()
    mock_frame.locator.return_value.inner_html = AsyncMock(return_value=flipp_html)
    # Also need to mock the wait_for on the locator
    mock_tile_locator = MagicMock()
    mock_tile_locator.first.wait_for = AsyncMock()
    mock_frame.locator.side_effect = lambda s: mock_tile_locator if "product-tile" in s else MagicMock(inner_html=AsyncMock(return_value=flipp_html))

    # Re-mocking to be more precise
    mock_html_locator = MagicMock()
    mock_html_locator.inner_html = AsyncMock(return_value=flipp_html)

    def frame_locator_side_effect(selector):
        if selector == "html":
            return mock_html_locator
        return mock_tile_locator

    mock_frame.locator.side_effect = frame_locator_side_effect
    mock_page.frame_locator.return_value = mock_frame

    # Act
    deals = await scraper._scrape_page(mock_page, limit=10)

    # Assert
    assert len(deals) == 1
    assert deals[0]["name"] == "Flipp Chicken"
    assert deals[0]["price"] == 10.00
    assert deals[0]["unit"] == "kg"

@pytest.mark.asyncio
async def test_iga_scraper_incapsula_detection():
    """
    Tests that IGA scraper detects Incapsula block.
    """
    scraper = IgaScraper()
    mock_page = MagicMock(spec=Page)

    mock_page.goto = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html><body>Incapsula incident ID: 12345</body></html>")

    # Act
    deals = await scraper._scrape_page(mock_page, limit=10)

    # Assert
    assert deals == []
