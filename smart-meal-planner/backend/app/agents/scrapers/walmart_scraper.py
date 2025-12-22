
from playwright.async_api import Page
from typing import List, Dict, Any
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import re
import logging

logger = logging.getLogger(__name__)

class WalmartScraper(BaseScraper):
    """
    Scraper for Walmart.ca.
    """
    STORE_NAME = "Walmart"

    async def _scrape_page(self, page: Page, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrapes the Walmart website for deals.
        """
        deals = []
        url = "https://www.walmart.ca/en/flyer"

        try:
            await page.goto(url, wait_until="networkidle", timeout=120000)
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            flyer_items = soup.select('[data-testid="flyer-item"]')

            for item in flyer_items:
                if len(deals) >= limit:
                    break

                try:
                    name = item.select_one('[data-testid="product-name"]').text.strip()
                    price_text = item.select_one('[data-testid="price-deal"]').text.strip()

                    price_match = re.search(r'(\d+\.\d{2})', price_text.replace(',', '.'))
                    price = float(price_match.group(1)) if price_match else 0.0

                    unit = "each"
                    if "/lb" in price_text:
                        unit = "lb"

                    deal = {
                        "name": name.strip(),
                        "price": price,
                        "original_price": price,
                        "unit": unit,
                        "store": self.STORE_NAME,
                        "category": "Flyer"
                    }
                    deals.append(deal)

                except Exception as e:
                    logger.error(f"Error scraping a flyer item: {e}")

        except Exception as e:
            logger.critical(f"A critical error occurred while scraping Walmart: {e}")

        return deals
