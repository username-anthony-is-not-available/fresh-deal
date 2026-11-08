from app.core.config import settings

from playwright.async_api import Page
from typing import List, Dict, Any, Optional
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import logging
import asyncio

logger = logging.getLogger(__name__)

class MetroScraper(BaseScraper):
    """
    Scraper for Metro.ca. This scraper is designed to handle the flyer page.
    """
    STORE_NAME = "Metro"

    def __init__(self, postal_code: Optional[str] = None, headless: bool = True, proxy_manager: Optional[Any] = None, storage_path: str = "/tmp"):
        postal_code = postal_code or getattr(settings, "LOCAL_POSTAL_CODE", None) or settings.DEFAULT_POSTAL_CODE
        super().__init__(postal_code, headless, proxy_manager, storage_path)

    async def _scrape_page(self, page: Page, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrapes the Metro website for deals.
        """
        deals = []
        urls = [
            "https://www.metro.ca/en/online-grocery/flyer",
            "https://www.metro.ca/en/flyer"
        ]

        for url in urls:
            if len(deals) >= limit:
                break
            try:
                logger.info(f"Navigating to Metro flyer page: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(5)

                # Check for bot detection
                if await self._check_incapsula_block(page):
                    logger.warning(f"Bot detection triggered on {url}")
                    continue

                # Handle cookie consent
                await self._handle_cookie_consent(page, '#onetrust-accept-btn-handler')

                # Scroll to load more products
                try:
                    await self._scroll_to_bottom(page, max_scrolls=3)
                except Exception as e:
                    logger.warning(f"Error while scrolling Metro: {e}")

                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')

                product_tiles = soup.select('div.default-product-tile.tile-product')
                if not product_tiles:
                    product_tiles = soup.select('div.product-tile-group__list__item')

                logger.info(f"Found {len(product_tiles)} product tiles on Metro at {url}.")

                for tile in product_tiles:
                    if len(deals) >= limit:
                        break

                    try:
                        deal = self._parse_tile(tile)
                        if deal and not any(d['name'] == deal['name'] for d in deals):
                            deals.append(deal)
                    except Exception as e:
                        logger.error(f"Error parsing a Metro product tile: {e}")

            except Exception as e:
                logger.error(f"Error scraping Metro URL {url}: {e}")
                continue

        if not deals:
            logger.warning("No deals found on any Metro URL. Saving debug info.")
            await self._save_debug_artifacts(page, "metro_debug")

        logger.info(f"Scraped {len(deals)} unique deals from Metro.")
        return deals

    def _parse_tile(self, tile: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """
        Parses a single Metro product tile.
        """
        # 1. Extract Name
        name_element = tile.select_one('span.head__title')
        if not name_element:
            name_element = tile.select_one('h3[class*="product-tile__name"]')

        if not name_element:
            # Try data attribute
            name = tile.get('data-product-name')
        else:
            name = name_element.get_text(strip=True)

        if not name:
            return None

        # 2. Extract Brand
        brand_element = tile.select_one('span.head__brand')
        brand = ""
        if brand_element:
            brand = brand_element.get_text(strip=True)
        elif tile.has_attr('data-product-brand'):
            brand = tile['data-product-brand']

        if brand and brand.lower() not in name.lower():
            name = f"{brand} {name}"

        # 3. Extract Price
        price_element = tile.select_one('div.pricing__sale-price span.price-update')
        if not price_element:
            price_element = tile.select_one('div.pricing__regular-price span.price-update')
        if not price_element:
            price_element = tile.select_one('span[class*="price__value"]')

        price = 0.0
        if price_element:
            price_text = price_element.get_text(strip=True)
            price = self._parse_price(price_text) or 0.0

        if price == 0.0:
            return None

        # 4. Extract Original Price
        original_price = price
        regular_price_element = tile.select_one('div.pricing__before-price')
        if regular_price_element:
            # Only take the span that doesn't have "Regular price" text
            spans = regular_price_element.find_all('span')
            for s in spans:
                if "$" in s.get_text():
                    original_price = self._parse_price(s.get_text()) or price
                    break

        # 5. Extract Unit
        unit_element = tile.select_one('span.head__unit-details')
        if not unit_element:
            unit_element = tile.select_one('span[class*="product-tile__package-size"]')

        unit_text = unit_element.get_text(strip=True).lower() if unit_element else ""
        unit = self._extract_unit(name + " " + unit_text)

        # 6. Extract Image
        image_element = tile.select_one('img')
        image_url = None
        if image_element:
            image_url = image_element.get('src') or image_element.get('data-src')

        return {
            "name": name,
            "price": round(price, 2),
            "original_price": round(original_price, 2),
            "unit": unit,
            "store": self.STORE_NAME,
            "image_url": image_url,
            "category": self._categorize_product(name),
            "sale_info": price_element.get_text(strip=True) if price_element else None
        }
