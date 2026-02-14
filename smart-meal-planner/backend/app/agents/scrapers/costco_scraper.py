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

        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Check for bot detection
            if await self._check_incapsula_block(page):
                return []

            # Handle cookie consent
            await self._handle_cookie_consent(page, 'button#onetrust-accept-btn-handler')

            while len(deals) < limit:
                try:
                    await page.wait_for_selector('[automation-id="product-tile"]', timeout=20000)
                except Exception:
                    break

                # Scroll to load lazy images/content
                await self._scroll_to_bottom(page, max_scrolls=2)

                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')

                product_tiles = soup.select('[automation-id="product-tile"]')
                if not product_tiles:
                    break

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

                    # Image
                    image_element = tile.select_one('img')
                    image_url = image_element['src'] if image_element and image_element.has_attr('src') else None

                    deal = {
                        "name": name,
                        "price": round(price, 2),
                        "original_price": round(price, 2),
                        "unit": self._extract_unit(name),
                        "store": self.STORE_NAME,
                        "image_url": image_url,
                        "category": self._categorize_product(name)
                    }
                    deals.append(deal)

                next_button = await page.query_selector('li.next a')
                if not next_button or len(deals) >= limit:
                    break

                await next_button.click()
                await page.wait_for_load_state('networkidle')
                await self._random_delay(2, 4)

        except Exception as e:
            print(f"Error scraping Costco: {e}")
            await self._save_debug_artifacts(page, "costco_error")

        return deals
