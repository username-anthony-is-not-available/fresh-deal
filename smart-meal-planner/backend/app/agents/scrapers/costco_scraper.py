from playwright.async_api import Page
from typing import List, Dict, Any
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import re

class CostcoScraper(BaseScraper):
    """
    Scraper for Costco.ca.
    """
    STORE_NAME = "Costco"

    async def _scrape_page(self, page: Page, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrapes the Costco website for deals.
        """
        deals = []
        url = "https://www.costco.ca/grocery-household.html"
        await page.goto(url, wait_until='domcontentloaded')

        while len(deals) < limit:
            await page.wait_for_selector('[automation-id="product-tile"]')
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            product_tiles = soup.select('[automation-id="product-tile"]')
            for tile in product_tiles:
                if len(deals) >= limit:
                    break

                name_element = tile.select_one('.description a')
                name = name_element.text.strip() if name_element else 'Unknown Product'

                price_element = tile.select_one('.price')

                price = 0.0
                if price_element:
                    price_text = price_element.text.strip()
                    price = self._parse_price(price_text) or 0.0

                if price == 0.0:
                    continue

                deal = {
                    "name": name,
                    "price": round(price, 2),
                    "original_price": round(price, 2),
                    "unit": self._extract_unit(name),
                    "store": self.STORE_NAME,
                    "category": self._categorize_product(name)
                }
                deals.append(deal)

            next_button = await page.query_selector('.next-page')
            if not next_button or len(deals) >= limit:
                break

            await next_button.click()
            await page.wait_for_load_state('domcontentloaded')

        return deals
