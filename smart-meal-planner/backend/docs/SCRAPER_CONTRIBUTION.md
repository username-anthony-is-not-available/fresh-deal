# Scraper Contribution Guide

Welcome! This guide explains how to add new grocery store scrapers to the Smart Meal Planner. We use **Playwright** for browser automation and **BeautifulSoup** for parsing.

## Architecture

All scrapers must inherit from `BaseScraper` located in `app/agents/scrapers/base_scraper.py`.

### The `BaseScraper` Class

`BaseScraper` provides common utilities and a standardized workflow:
1. **`scrape(limit)`**: The entry point. It sets up the browser context (with stealth measures and proxies), calls `_scrape_page`, and handles cleanup.
2. **`_scrape_page(page, limit)`**: **(Must be implemented)** This is where the navigation and extraction logic resides.
3. **`_parse_tile(tile)`**: A recommended helper method to parse individual product elements (tiles).

## Implementing a New Scraper

### 1. Basic Structure

Create a new file in `app/agents/scrapers/` (e.g., `my_store_scraper.py`):

```python
from playwright.async_api import Page
from typing import List, Dict, Any, Optional
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

class MyStoreScraper(BaseScraper):
    STORE_NAME = "MyStore"

    async def _scrape_page(self, page: Page, limit: int = 50) -> List[Dict[str, Any]]:
        deals = []
        url = "https://www.mystore.ca/flyer"

        await page.goto(url, wait_until="networkidle")

        # Handle lazy loading
        await self._scroll_to_bottom(page)

        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')

        # Select product tiles
        tiles = soup.select('.product-tile')

        for tile in tiles:
            if len(deals) >= limit: break
            deal = self._parse_tile(tile)
            if deal:
                deals.append(deal)

        return deals

    def _parse_tile(self, tile: BeautifulSoup) -> Optional[Dict[str, Any]]:
        # Use BaseScraper utilities for parsing
        name = tile.select_one('.name').text.strip()
        price_text = tile.select_one('.price').text.strip()
        price = self._parse_price(price_text)

        if not price: return None

        return {
            "name": name,
            "price": price,
            "store": self.STORE_NAME,
            "unit": self._extract_unit(name),
            "category": self._categorize_product(name)
        }
```

### 2. Handling Lazy Loading

Many grocery websites load content as you scroll. Use the built-in utility:

```python
await self._scroll_to_bottom(page, max_scrolls=5)
```

### 3. Flipp Integration

Many Quebec retailers (IGA, Provigo, etc.) use Flipp for their flyers, often embedded in an iframe. `BaseScraper` provides a specialized method for this:

```python
# In _scrape_page:
product_tiles = await self._scrape_flipp_frame(page)
# This returns a list of BeautifulSoup objects for each product tile found in the iframe.
```

### 4. Anti-Bot Measures

The `BaseScraper` handles most stealth measures automatically. However, you should always check for blocks after navigation:

```python
if await self._check_incapsula_block(page):
    logger.error("Blocked by Incapsula")
    return []
```

### 5. Parsing Utilities

Always use these `BaseScraper` methods to ensure consistency:
- `_parse_price(text)`: Handles "$2.99", "2 pour 5$", "88¢", etc.
- `_extract_unit(text)`: Extracts units like "kg", "lb", "pack" from names or descriptions.
- `_categorize_product(name)`: Automatically assigns a category (e.g., "Dairy & Eggs") based on the product name.

## Local Verification

We use **Regression Tests** with static HTML snapshots to verify scrapers without hitting live websites.

### 1. Create an HTML Snapshot
Save the flyer's HTML content to `tests/e2e/snapshots/mock_mystore_flyer.html`.

### 2. Add a Regression Test
In `tests/test_scraper_regression.py`, add a test case:

```python
@pytest.mark.asyncio
async def test_mystore_regression():
    content = get_snapshot_content("mock_mystore_flyer.html")
    page = await mock_page_with_content(content)

    scraper = MyStoreScraper()
    deals = await scraper._scrape_page(page, limit=10)

    assert len(deals) > 0
    assert deals[0]["name"] == "Expected Name"
    assert deals[0]["price"] == 1.99
```

### 3. Run the Tests
```bash
export PYTHONPATH=.
python -m pytest tests/test_scraper_regression.py
```

## Best Practices
- **Fallback Selectors**: Websites change often. Use multiple selectors for key elements.
- **Wait Strategically**: Use `page.wait_for_selector()` instead of fixed `sleep()` where possible.
- **Log Errors**: Use `logger.error` in try-except blocks within `_parse_tile` to avoid one bad tile breaking the whole scrape.
