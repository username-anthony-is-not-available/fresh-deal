
from playwright.async_api import Page
from typing import List, Dict, Any
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

class MetroScraper(BaseScraper):
    """
    Scraper for Metro.ca. This scraper is designed to handle the flyer page.
    """
    STORE_NAME = "Metro"

    async def _scrape_page(self, page: Page, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrapes the Metro website for deals.
        """
        deals = []
        url = "https://www.metro.ca/en/online-grocery/flyer"

        try:
            logger.info("Navigating to the Metro flyer page.")
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Handle cookie consent
            await self._handle_cookie_consent(page, '#onetrust-accept-btn-handler')

            # Scroll to load more products
            await self._scroll_to_bottom(page, max_scrolls=5)

            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            product_tiles = soup.select('div[class*="product-tile-group__list__item"]')
            logger.info(f"Found {len(product_tiles)} product tiles on Metro.")

            if not product_tiles:
                logger.warning("No product tiles found on the Metro page. Saving debug info.")
                await self._save_debug_artifacts(page, "metro_debug")
                return []

            for tile in product_tiles:
                if len(deals) >= limit:
                    break

                try:
                    name_element = tile.select_one('h3[class*="product-tile__name"]')
                    price_element = tile.select_one('span[class*="price__value"]')
                    image_element = tile.select_one('img[class*="product-tile__image__image"]')

                    if not name_element:
                        continue

                    name = name_element.text.strip()

                    price = 0.0
                    if price_element:
                        price_text = price_element.text.strip()
                        price = self._parse_price(price_text) or 0.0

                    if price == 0.0:
                        continue

                    image_url = image_element['src'] if image_element and image_element.has_attr('src') else None

                    unit_element = tile.select_one('span[class*="product-tile__package-size"]')
                    unit_text = unit_element.text.strip().lower() if unit_element else ""
                    unit = self._extract_unit(name + " " + unit_text)

                    deal = {
                        "name": name,
                        "price": round(price, 2),
                        "original_price": round(price, 2),
                        "unit": unit,
                        "store": self.STORE_NAME,
                        "image_url": image_url,
                        "category": self._categorize_product(name)
                    }
                    deals.append(deal)
                except Exception as e:
                    logger.error(f"Error parsing a Metro product tile: {e}")

        except Exception as e:
            logger.critical(f"A critical error occurred while scraping Metro: {e}")
            await self._save_debug_artifacts(page, "metro_critical_error")

        logger.info(f"Scraped {len(deals)} deals from Metro.")
        return deals
