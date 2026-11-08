from app.core.config import settings

from playwright.async_api import Page
from typing import List, Dict, Any, Optional
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import logging
import asyncio
import re

logger = logging.getLogger(__name__)

class ProvigoScraper(BaseScraper):
    """
    Scraper for Provigo.ca. This scraper is designed to handle the flyer page,
    including the Flipp iframe integration.
    """
    STORE_NAME = "Provigo"

    def __init__(self, postal_code: Optional[str] = None, headless: bool = True, proxy_manager: Optional[Any] = None, storage_path: str = "/tmp"):
        postal_code = postal_code or getattr(settings, "LOCAL_POSTAL_CODE", None) or settings.DEFAULT_POSTAL_CODE
        super().__init__(postal_code, headless, proxy_manager, storage_path)

    async def _scrape_page(self, page: Page, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrapes the Provigo website for deals.
        """
        deals = []
        urls = [
            "https://www.provigo.ca/en/deals/flyer",
            "https://www.provigo.ca/en/flyer",
            "https://www.provigo.ca/en/collection/deals-centre"
        ]

        seen_names = set()

        for url in urls:
            if len(deals) >= limit:
                break

            try:
                logger.info(f"Navigating to Provigo flyer page: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(10)

                # Check for bot detection
                if await self._check_incapsula_block(page):
                    logger.warning(f"Bot detection triggered on {url}")
                    continue

                # Handle cookie consent
                await self._handle_cookie_consent(page, '#onetrust-accept-btn-handler')

                # Handle location confirmation if it appears
                try:
                    yes_button = page.get_by_role("button", name="Yes")
                    if await yes_button.is_visible(timeout=5000):
                        await yes_button.click()
                        await asyncio.sleep(2)
                except Exception:
                    pass

                # Wait for loading spinner to disappear
                try:
                    await page.wait_for_selector('div.loading--spinner', state='hidden', timeout=20000)
                except Exception:
                    pass

                # Wait for content to appear
                try:
                    await page.wait_for_selector('[data-testid="product-title"]', timeout=20000)
                except Exception:
                    pass

                # Check for Flipp iframe (some pages might still use it)
                iframe_tiles = await self._scrape_flipp_frame(page)
                for tile in iframe_tiles:
                    deal = self._parse_tile(tile)
                    if deal and deal['name'] not in seen_names:
                        deals.append(deal)
                        seen_names.add(deal['name'])
                        if len(deals) >= limit:
                            break

                # Scroll to load more native content
                await self._scroll_to_bottom(page, max_scrolls=3)

                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')

                # Find native tiles
                product_tiles = soup.select('[data-testid="product-grid-component"]')
                if not product_tiles:
                    product_tiles = soup.select('div.chakra-linkbox')
                if not product_tiles:
                    product_tiles = soup.select('div[class*="product-tile"]')

                logger.info(f"Found {len(product_tiles)} potential native product tiles on Provigo at {url}.")

                for tile in product_tiles:
                    if len(deals) >= limit:
                        break

                    try:
                        deal = self._parse_tile(tile)
                        if deal and deal['name'] not in seen_names:
                            deals.append(deal)
                            seen_names.add(deal['name'])
                    except Exception as e:
                        logger.debug(f"Error parsing a Provigo product tile: {e}")

            except Exception as e:
                logger.error(f"Error scraping Provigo URL {url}: {e}")
                continue

        if not deals:
            logger.warning("No deals found on any Provigo URL. Saving debug info.")
            await self._save_debug_artifacts(page, "provigo_debug")

        logger.info(f"Scraped {len(deals)} unique deals from Provigo.")
        return deals

    def _parse_tile(self, tile: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """
        Parses a single Provigo product tile, supporting both Flipp and native selectors.
        """
        # 1. Extract Name
        name_element = (
            tile.select_one('[data-testid="product-title"]') or
            tile.select_one('h3[class*="product-tile__name"]') or
            tile.select_one('h3')
        )
        if not name_element:
            return None
        name = name_element.get_text(strip=True)

        # 2. Extract Brand
        brand_element = tile.select_one('[data-testid="product-brand"]')
        brand = brand_element.get_text(strip=True) if brand_element else ""
        if brand and brand.lower() not in name.lower():
            name = f"{brand} {name}"

        # 3. Extract Price
        price_element = (
            tile.select_one('[data-testid="price-product-tile"]') or
            tile.select_one('[data-testid="sale-price"]') or
            tile.select_one('[data-testid="regular-price"]') or
            tile.select_one('.price__value') or
            tile.select_one('span[class*="price__value"]')
        )

        price = 0.0
        if price_element:
            price_text = price_element.get_text(separator=" ", strip=True)
            # Remove "sale", "was", etc.
            price_text = re.sub(r'(?i)sale|was|save|member price', '', price_text).strip()
            price = self._parse_price(price_text) or 0.0

        if price == 0.0:
            return None

        # 4. Extract Original Price
        original_price = price
        was_price_element = tile.select_one('span:contains("was")') or tile.select_one('.was-price')
        if was_price_element:
            original_price = self._parse_price(was_price_element.get_text()) or price

        # 5. Extract Unit/Package Size
        unit_element = (
            tile.select_one('[data-testid="product-package-size"]') or
            tile.select_one('.product-tile__package-size') or
            tile.select_one('span[class*="product-tile__package-size"]')
        )

        unit_text = unit_element.get_text(strip=True).lower() if unit_element else ""
        unit = self._extract_unit(name + " " + unit_text + " " + (price_element.get_text() if price_element else ""))

        # 6. Extract Loyalty Info
        loyalty_info = self._parse_loyalty_points(tile.get_text(separator=" "))
        loyalty_program, loyalty_points = loyalty_info if loyalty_info else (None, None)

        # 7. Extract Image
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
            "loyalty_program": loyalty_program,
            "loyalty_points": loyalty_points,
            "sale_info": price_element.get_text(separator=" ", strip=True) if price_element else None
        }
