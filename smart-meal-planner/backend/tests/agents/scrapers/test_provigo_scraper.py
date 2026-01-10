
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

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
    with open('smart-meal-planner/backend/provigo_critical_error.html', 'r', encoding='utf-8') as f:
        html_content = f.read()
    mock_page.content = AsyncMock(return_value=html_content)

    # Mock screenshot and other methods that might be called on failure
    mock_page.screenshot = AsyncMock(return_value=None)

    # Mock the frame_locator call to simulate a timeout, as the iframe content won't be in the static file
    mock_frame_locator = MagicMock()
    mock_frame_locator.locator().first.wait_for = AsyncMock(side_effect=asyncio.TimeoutError("Simulated timeout waiting for iframe content"))
    mock_page.frame_locator.return_value = mock_frame_locator

    return mock_page

@patch('playwright.async_api._generated.Browser.new_context')
@patch('playwright.async_api._generated.BrowserContext.new_page')
@patch('playwright.async_api._generated.Playwright.chromium.launch')
async def test_scrape_handles_timeout_gracefully(mock_launch, mock_new_page, mock_new_context, mock_playwright_page):
    """
    Tests that the ProvigoScraper returns an empty list when it can't find
    the necessary elements in the iframe (simulating a timeout or anti-bot page).
    """
    # Arrange
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_launch.return_value = mock_browser
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_playwright_page
    mock_context.storage_state.return_value = {}

    scraper = ProvigoScraper(headless=True)

    # Act
    deals = await scraper.scrape(limit=10)

    # Assert
    assert deals == []

    # Verify that the scraper tried to navigate to the correct URL
    mock_playwright_page.goto.assert_called_once_with("https://www.provigo.ca/en/flyer", wait_until="networkidle", timeout=60000)

    # Verify that it tried to find the iframe, leading to the simulated timeout
    mock_playwright_page.frame_locator.assert_called_once_with('iframe[title="Main Panel"]')
