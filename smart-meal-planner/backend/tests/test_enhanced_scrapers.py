import pytest
from playwright.async_api import Page
from typing import List, Dict, Any
from app.agents.scrapers.costco_scraper import CostcoScraper
from app.agents.scrapers.adonis_scraper import AdonisScraper
from unittest.mock import AsyncMock, MagicMock, patch
from bs4 import BeautifulSoup

@pytest.mark.asyncio
async def test_costco_scraper_parsing_logic():
    """
    Tests the parsing logic of the CostcoScraper using mock HTML content.
    """
    scraper = CostcoScraper()
    mock_page = MagicMock(spec=Page)

    mock_html = """
    <html>
        <body>
            <div automation-id="product-tile">
                <div class="description"><a href="#">Organic Blueberries</a></div>
                <div class="price">$12.99</div>
                <img src="http://example.com/blueberries.jpg" />
            </div>
            <div automation-id="product-tile">
                <div class="description"><a href="#">Kirkland Signature Chicken</a></div>
                <div class="price">$25.00</div>
                <img src="http://example.com/chicken.jpg" />
            </div>
        </body>
    </html>
    """

    mock_page.goto = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.content = AsyncMock(return_value=mock_html)
    mock_page.evaluate = AsyncMock(return_value=1000)
    mock_page.is_visible = AsyncMock(return_value=False)
    mock_page.query_selector = AsyncMock(return_value=None)

    # Act
    deals = await scraper._scrape_page(mock_page, limit=10)

    # Assert
    assert len(deals) == 2
    assert deals[0]["name"] == "Organic Blueberries"
    assert deals[0]["price"] == 12.99
    assert deals[0]["image_url"] == "http://example.com/blueberries.jpg"
    assert deals[1]["name"] == "Kirkland Signature Chicken"
    assert deals[1]["price"] == 25.00
    assert deals[1]["store"] == "Costco"

@pytest.mark.asyncio
async def test_adonis_scraper_delegation():
    """
    Tests that AdonisScraper correctly delegates to FlippScraper.
    """
    with patch('app.agents.flipp_scraper.FlippScraper.scrape', new_callable=AsyncMock) as mock_scrape:
        mock_scrape.return_value = [{"name": "Adonis Pita", "price": 2.99, "store": "Adonis"}]

        scraper = AdonisScraper(postal_code="H4T1V6")
        deals = await scraper.scrape(limit=5)

        assert len(deals) == 1
        assert deals[0]["name"] == "Adonis Pita"
        mock_scrape.assert_called_once()
