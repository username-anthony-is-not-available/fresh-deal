from playwright.async_api import async_playwright
from typing import List, Dict, Any
from .base_scraper import BaseScraper
import re
import asyncio
import logging

# Use getLogger to ensure logging is configured at the application level
logger = logging.getLogger(__name__)

class WalmartScraper(BaseScraper):
    """
    Scraper for Walmart.ca.
    """
    STORE_NAME = "Walmart"

    async def scrape(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrapes the Walmart website for deals.
        """
        async with async_playwright() as p:
            browser = await self._get_browser(p)
            context = await self._get_context(browser)
            page = await self._get_page(context)

            deals = []
            # Updated URL to target the general flyer
            url = "https://www.walmart.ca/en/flyer"

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=120000)

                # The flyer page might have a different structure, so we adapt
                # We will look for items within the flyer grid
                flyer_items = await page.locator('[data-testid="flyer-item"]').all()

                for item in flyer_items:
                    if len(deals) >= limit:
                        break

                    try:
                        name = await item.locator('[data-testid="product-name"]').inner_text()
                        price_text = await item.locator('[data-testid="price-deal"]').inner_text()

                        price_match = re.search(r'\d+\.\d{2}', price_text.replace(',', '.'))
                        price = float(price_match.group(0)) if price_match else 0.0

                        # Flyer items might not have original price or unit, so we handle that
                        original_price = price
                        unit = "each"

                        deal = {
                            "name": name.strip(),
                            "price": price,
                            "original_price": original_price,
                            "unit": unit,
                            "store": self.STORE_NAME,
                            "category": "Flyer"
                        }
                        deals.append(deal)

                    except Exception as e:
                        logger.error(f"Error scraping a flyer item: {e}")

            except Exception as e:
                logger.critical(f"A critical error occurred while scraping Walmart flyer: {e}")
            finally:
                await browser.close()

            return deals
