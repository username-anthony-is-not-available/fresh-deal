
import pytest
from app.agents.scrapers.adonis_scraper import AdonisScraper
from unittest.mock import patch, MagicMock
import asyncio

@pytest.mark.asyncio
async def test_adonis_scraper_mock():
    with patch('app.agents.flipp_scraper.FlippScraper.search') as mock_search:
        mock_search.return_value = [
            {
                "name": "Feta Cheese",
                "category": "Dairy & Eggs",
                "price": 5.99,
                "original_price": 7.99,
                "unit": "each",
                "store": "Adonis",
                "image_url": "https://example.com/feta.jpg"
            }
        ]

        scraper = AdonisScraper(postal_code="H4T1V6")
        deals = await scraper.scrape(limit=10, search_terms=["cheese"])

        assert len(deals) == 1
        assert deals[0]["name"] == "Feta Cheese"
        assert deals[0]["store"] == "Adonis"
