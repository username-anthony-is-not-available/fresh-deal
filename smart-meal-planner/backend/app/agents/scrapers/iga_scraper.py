from app.core.config import settings

from playwright.async_api import Page
from typing import List, Dict, Any, Optional
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

class IgaScraper(BaseScraper):
    """
    A functional scraper for IGA.net that handles the online flyer.
    """
    STORE_NAME = "IGA"

    def __init__(self, postal_code: Optional[str] = None, headless: bool = True, proxy_manager: Optional[Any] = None, storage_path: str = "/tmp"):
        postal_code = postal_code or getattr(settings, "LOCAL_POSTAL_CODE", None) or settings.DEFAULT_POSTAL_CODE
        super().__init__(postal_code, headless, proxy_manager, storage_path)

    async def _scrape_page(self, page: Page, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrapes the IGA website for deals by navigating to the flyer page,
        handling cookies, and parsing product information.
        """
        deals = []
        url = "https://www.iga.net/en/online-flyer"

        try:
            logger.info("Navigating to the IGA flyer page.")
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await self._random_delay(2, 5)

            # Detect Incapsula block
            if await self._check_incapsula_block(page):
                logger.critical("IGA access denied by Incapsula.")
                return []

            # Handle the cookie consent button
            await self._handle_cookie_consent(page, 'button:has-text("Accept All")')

            # Use centralized Flipp frame scraper
            product_tiles = await self._scrape_flipp_frame(page)

            if not product_tiles:
                # Fallback to main page content
                logger.info("Flipp frame not found on IGA, looking for native tiles.")
                try:
                    await page.wait_for_selector('div[class*="product-tile-wrapper"]', timeout=15000)
                except Exception:
                    pass
                await self._scroll_to_bottom(page, max_scrolls=5)
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                product_tiles = soup.select('div[class*="product-tile-wrapper"]')

            if not product_tiles:
                logger.warning("No product tiles found on the IGA page. Saving debug info.")
                await self._save_debug_artifacts(page, "iga_debug")
                return []

            for tile in product_tiles:
                if len(deals) >= limit:
                    break

                try:
                    deal = self._parse_tile(tile)
                    if deal:
                        deals.append(deal)
                except Exception as e:
                    logger.error(f"Error parsing an IGA product tile: {e}")

        except Exception as e:
            logger.critical(f"A critical error occurred while scraping IGA: {e}")
            await self._save_debug_artifacts(page, "iga_critical_error")

        logger.info(f"Successfully scraped {len(deals)} deals from IGA.")
        return deals

    def _parse_tile(self, tile: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """
        Parses a single product tile for IGA, supporting both native and Flipp selectors.
        """
        # 1. Extract Name
        name_element = tile.select_one('h3[class*="product-tile-name"]') # Native
        if not name_element:
            name_element = tile.select_one('[data-testid="product-title"]') # Flipp

        if not name_element:
            return None

        name = name_element.text.strip()

        # 2. Extract Price
        price_element = tile.select_one('div[class*="product-tile-price"]') # Native
        if not price_element:
            price_element = tile.select_one('.price__value') # Flipp

        price = 0.0
        if price_element:
            price_text = price_element.text.strip()
            price = self._parse_price(price_text) or 0.0

        if price == 0.0:
            return None

        # 3. Handle package size/unit
        unit_element = tile.select_one('div[class*="product-tile-package-size"]') # Native
        if not unit_element:
            unit_element = tile.select_one('.product-tile__package-size') # Flipp

        unit_text = unit_element.text.strip().lower() if unit_element else ""
        unit = self._extract_unit(name + " " + unit_text)

        # Handle image
        image_element = tile.select_one('img[class*="product-tile-image"]')
        image_url = None
        if image_element:
            if image_element.has_attr('src'):
                image_url = image_element['src']
            elif image_element.has_attr('data-src'):
                image_url = image_element['data-src']

        return {
            "name": name,
            "price": round(price, 2),
            "original_price": round(price, 2),
            "unit": unit,
            "store": self.STORE_NAME,
            "image_url": image_url,
            "category": self._categorize_product(name),
            "sale_info": price_element.text.strip() if price_element else None
        }
