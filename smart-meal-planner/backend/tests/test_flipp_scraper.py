
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.agents.flipp_scraper import FlippScraper

@pytest.fixture
def scraper():
    return FlippScraper(postal_code="H1A1A1")

@pytest.mark.asyncio
async def test_parse_flyer_item(scraper: FlippScraper):
    # Arrange
    flyer_item_data = {
        "name": "Organic Bananas",
        "merchant_name": "Metro",
        "current_price": 0.99,
        "original_price": 1.99,
        "post_price_text": "/lb",
        "_L1": "Grocery",
        "_L2": "Fruits",
    }

    # Act
    parsed_item = scraper._parse_flyer_item(flyer_item_data)

    # Assert
    assert parsed_item is not None
    assert parsed_item["name"] == "Organic Bananas"
    assert parsed_item["store"] == "Metro"
    assert parsed_item["price"] == 0.99
    assert parsed_item["original_price"] == 1.99
    assert parsed_item["unit"] == "lb"
    assert parsed_item["category"] == "Fruits"

@pytest.mark.asyncio
async def test_parse_flyer_item_invalid_price(scraper: FlippScraper):
    # Arrange
    flyer_item_data = {"name": "Invalid Item", "current_price": None}

    # Act
    parsed_item = scraper._parse_flyer_item(flyer_item_data)

    # Assert
    assert parsed_item is None

@pytest.mark.asyncio
async def test_search_with_mock_session(scraper: FlippScraper):
    # Arrange
    mock_response = MagicMock()
    mock_response.status = 200
    # The response from the real API is a JSON object with an 'items' key
    mock_response.json = AsyncMock(return_value={
        "items": [
            {
                "name": "Chicken Breast",
                "merchant_name": "Walmart",
                "current_price": 5.00,
            }
        ],
        "ecom_items": []
    })

    mock_session = MagicMock()
    # The session is used as an async context manager
    mock_session.get.return_value.__aenter__.return_value = mock_response

    # Act
    results = await scraper.search("chicken", mock_session)

    # Assert
    assert len(results) == 1
    assert results[0]["name"] == "Chicken Breast"
    assert results[0]["store"] == "Walmart"
    assert results[0]["price"] == 5.00
    mock_session.get.assert_called_once()

@pytest.mark.asyncio
async def test_full_scrape_with_mocking(scraper: FlippScraper):
    # Arrange
    # Since scrape calls search, we can mock search directly
    scraper.search = AsyncMock(return_value=[
        {"name": "Apples", "store": "Maxi", "price": 2.99}
    ])

    # Act
    items = await scraper.scrape(limit=10, search_terms=["apples"])

    # Assert
    assert len(items) == 1
    assert items[0]["name"] == "Apples"
    # The second argument is the aiohttp.ClientSession, which is created inside the scrape method.
    # We can just check that the first argument is correct.
    scraper.search.assert_called_once()
    assert scraper.search.call_args[0][0] == "apples"
