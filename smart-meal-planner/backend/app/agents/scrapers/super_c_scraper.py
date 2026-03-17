
from playwright.async_api import Page
from typing import List, Dict, Any, Optional
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

class SuperCScraper(BaseScraper):
    """
    Scraper for SuperC.ca. Handles the flyer page and Flipp iframe integration.
    """
    STORE_NAME = "Super C"

    def __init__(self, postal_code: str = "H4T1V6", headless: bool = True, proxy_manager: Optional[Any] = None, storage_path: str = "/tmp"):
        super().__init__(postal_code, headless, proxy_manager, storage_path)

    async def _scrape_page(self, page: Page, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrapes the Super C website for deals.
        """
        deals = []
        url = "https://www.superc.ca/en/flyer"

        try:
            logger.info(f"Navigating to {self.STORE_NAME} flyer page.")
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await self._random_delay(2, 5)

            # Detect Incapsula block
            if await self._check_incapsula_block(page):
                logger.critical(f"{self.STORE_NAME} access denied by Incapsula.")
                return []

            # Handle cookie consent
            await self._handle_cookie_consent(page, '#onetrust-accept-btn-handler')

            # Use centralized Flipp frame scraper
            product_tiles = await self._scrape_flipp_frame(page)

            if not product_tiles:
                # Fallback to direct tiles if Flipp frame not found
                logger.info("Flipp frame not found on Super C, looking for native tiles.")
                await page.wait_for_selector('div[class*="product-tile"]', timeout=10000)
                await self._scroll_to_bottom(page, max_scrolls=3)
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                product_tiles = soup.select('div[class*="product-tile"]')

            logger.info(f"Found {len(product_tiles)} product tiles on {self.STORE_NAME}.")

            if not product_tiles:
                logger.warning(f"No product tiles found on the {self.STORE_NAME} page. Saving debug info.")
                await self._save_debug_artifacts(page, "superc_debug")
                return []

            for tile in product_tiles:
                if len(deals) >= limit:
                    break

                try:
                    deal = self._parse_tile(tile)
                    if deal:
                        deals.append(deal)
                except Exception as e:
                    logger.error(f"Error parsing a {self.STORE_NAME} product tile: {e}")

        except Exception as e:
            logger.critical(f"A critical error occurred while scraping {self.STORE_NAME}: {e}")
            await self._save_debug_artifacts(page, "superc_critical_error")

        logger.info(f"Scraped {len(deals)} deals from {self.STORE_NAME}.")
        return deals

    def _parse_tile(self, tile: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """
        Parses a single product tile, supporting both Flipp and native selectors.
        """
        # 1. Extract Name
        name_element = tile.select_one('[data-testid="product-title"]') # Flipp
        if not name_element:
            name_element = tile.select_one('h3[class*="product-tile__name"]') # Native

        if not name_element:
            return None
        name = name_element.get_text(strip=True)

        # 2. Extract Price
        price_element = tile.select_one('.price__value') # Both Flipp and Native often use this
        if not price_element:
            price_element = tile.select_one('span[class*="price__value"]')
        if not price_element:
            price_element = tile.select_one('[data-testid="sale-price"]')

        price = 0.0
        if price_element:
            price_text = price_element.get_text(strip=True)
            price = self._parse_price(price_text) or 0.0

        if price == 0.0:
            return None

        # 3. Extract Unit/Package Size
        unit_element = tile.select_one('.product-tile__package-size') # Flipp
        if not unit_element:
            unit_element = tile.select_one('span[class*="product-tile__package-size"]') # Native

        unit_text = unit_element.get_text(strip=True).lower() if unit_element else ""
        unit = self._extract_unit(name + " " + unit_text)

        # 4. Extract Image
        image_element = tile.select_one('img')
        image_url = None
        if image_element:
            image_url = image_element.get('src') or image_element.get('data-src')

        return {
            "name": name,
            "price": round(price, 2),
            "original_price": round(price, 2),
            "unit": unit,
            "store": self.STORE_NAME,
            "image_url": image_url,
            "category": self._categorize_product(name)
        }
