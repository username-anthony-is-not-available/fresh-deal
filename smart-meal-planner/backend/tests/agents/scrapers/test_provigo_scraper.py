import pytest
import asyncio
from unittest.mock import AsyncMock

from app.agents.scrapers.provigo_scraper import ProvigoScraper

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_playwright_page():
    """Fixture to create a mock Playwright Page object."""
    mock_page = AsyncMock()

    # Mock the goto method
    mock_page.goto = AsyncMock(return_value=None)

    # Mock the content method to return the saved HTML content
    with open("provigo_critical_error.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    mock_page.content = AsyncMock(return_value=html_content)

    # Mock screenshot and other methods that might be called on failure
    mock_page.screenshot = AsyncMock(return_value=None)

    # The current Provigo scraper waits for product tiles; simulate a timeout.
    mock_page.wait_for_selector = AsyncMock(
        side_effect=asyncio.TimeoutError("Simulated timeout waiting for product tiles")
    )

    return mock_page


async def test_scrape_handles_timeout_gracefully(mock_playwright_page):
    """Returns an empty list when Provigo product tiles never appear."""
    scraper = ProvigoScraper(headless=True)

    deals = await scraper._scrape_page(mock_playwright_page, limit=10)

    assert deals == []
    mock_playwright_page.goto.assert_called_once_with(
        "https://www.provigo.ca/en/flyer", wait_until="networkidle", timeout=60000
    )
