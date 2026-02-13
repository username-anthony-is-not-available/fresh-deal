
from playwright.async_api import Page
from typing import List, Dict, Any, Optional
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import re
import os
import logging
import asyncio

logger = logging.getLogger(__name__)

class MaxiScraper(BaseScraper):
    """
    Scraper for Maxi.ca. This scraper handles the flyer page,
    including location settings for Montreal and Flipp iframe integration.
    """
    STORE_NAME = "Maxi"

    def __init__(self, headless: bool = True, postal_code: str = "H2X 1Y1", proxy_manager: Optional[Any] = None, storage_path: str = "/tmp"):
        super().__init__(headless, proxy_manager, storage_path)
        self.postal_code = postal_code

    async def _scrape_page(self, page: Page, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrapes the Maxi website for deals.
        """
        deals = []
        # Try multiple URLs for the flyer
        urls = [
            "https://www.maxi.ca/en/deals/flyer",
            "https://www.maxi.ca/en/flyer"
        ]

        success = False
        for url in urls:
            try:
                logger.info(f"Navigating to {self.STORE_NAME} flyer page: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await self._random_delay(2, 5)

                # Handle cookie consent
                await self._handle_cookie_consent(page)

                # Handle location setting
                await self._handle_location(page)

                # Wait for content
                logger.info("Waiting for flyer content to load.")
                flyer_frame_selector = 'iframe[title="Main Panel"]'
                native_tile_selector = 'div[class*="product-tile"], div[data-testid="product-tile"]'

                # Try to wait for tiles
                try:
                    await page.wait_for_selector(f'{flyer_frame_selector}, {native_tile_selector}', timeout=20000)
                except Exception:
                    # If tiles not found, maybe scroll to trigger load
                    await page.evaluate("window.scrollTo(0, 500);")
                    await asyncio.sleep(2)

                # Extract tiles from iframe or main page
                product_tiles = []

                # Check Flipp iframe
                flyer_frame = page.frame_locator(flyer_frame_selector)
                try:
                    if await flyer_frame.locator('div[data-testid="product-tile"]').count() > 0:
                        logger.info(f"Found Flipp flyer frame on {self.STORE_NAME}.")
                        frame_content = await flyer_frame.locator('html').inner_html()
                        soup = BeautifulSoup(frame_content, 'html.parser')
                        product_tiles = soup.select('div[data-testid="product-tile"]')
                except Exception:
                    product_tiles = []

                if not product_tiles:
                    # Check native
                    content = await page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    product_tiles = soup.select(native_tile_selector)
                    if product_tiles:
                        logger.info(f"Found {len(product_tiles)} native product tiles on {self.STORE_NAME}.")

                if product_tiles:
                    for tile in product_tiles:
                        if len(deals) >= limit:
                            break
                        try:
                            deal = self._parse_tile(tile)
                            if deal:
                                deals.append(deal)
                        except Exception as e:
                            logger.error(f"Error parsing a {self.STORE_NAME} tile: {e}")

                    if deals:
                        success = True
                        break
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                continue

        if not success:
            logger.warning("No deals found on flyer pages. Trying 'Deals Centre' as fallback.")
            try:
                await page.goto("https://www.maxi.ca/en/collection/deals-centre", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(5)
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                product_tiles = soup.select('div[class*="product-tile"], div[data-testid="product-tile"]')
                for tile in product_tiles:
                    if len(deals) >= limit:
                        break
                    deal = self._parse_tile(tile)
                    if deal:
                        deals.append(deal)
            except Exception as e:
                logger.error(f"Fallback scraping failed: {e}")

        if not deals:
            await self._save_debug_info(page, "maxi_debug")

        logger.info(f"Scraped total of {len(deals)} deals from {self.STORE_NAME}.")
        return deals

    async def _handle_cookie_consent(self, page: Page):
        try:
            selector = '#onetrust-accept-btn-handler'
            if await page.is_visible(selector, timeout=5000):
                await page.click(selector)
                await asyncio.sleep(1)
        except Exception:
            pass

    async def _handle_location(self, page: Page):
        """
        Attempts to set the location to Montreal.
        """
        try:
            # Common Loblaw store picker selectors
            picker_selectors = [
                'button[class*="location-picker"]',
                'button[class*="store-picker"]',
                '.header-store-picker__button',
                'button:has-text("Store")'
            ]

            picker = None
            for sel in picker_selectors:
                if await page.is_visible(sel, timeout=2000):
                    picker = sel
                    break

            if picker:
                await page.click(picker)
                await asyncio.sleep(2)

                # Find input
                input_sel = 'input[id="location-search"], input[placeholder*="Postal"], input[name*="search-zip"]'
                await page.wait_for_selector(input_sel, timeout=5000)
                await page.fill(input_sel, self.postal_code)
                await page.keyboard.press("Enter")
                await asyncio.sleep(3)

                # Click first store result
                set_store_sel = 'button:has-text("Set as my store"), button:has-text("Select")'
                if await page.is_visible(set_store_sel, timeout=5000):
                    await page.click(set_store_sel)
                    await asyncio.sleep(2)
        except Exception:
            pass

    def _parse_tile(self, tile: BeautifulSoup) -> Optional[Dict[str, Any]]:
        # Same parsing logic as before, but a bit more robust
        name_element = tile.select_one('[data-testid="product-title"], h3[class*="product-tile__name"], .product-name, [class*="product-title"]')
        if not name_element:
            return None
        name = name_element.text.strip()

        price_element = tile.select_one('.price__value, span[class*="price__value"], .price, [class*="price__value"]')
        if not price_element:
            return None
        price_text = price_element.text.strip()

        # Extract current price
        price = 0.0
        if "for" in price_text.lower() or "/" in price_text:
            multi_buy_match = re.search(r'(\d+)\s*(?:for|/)\s*[\$]?\s*(\d+[\.,]\d{2})', price_text.lower())
            if multi_buy_match:
                try:
                    quantity = int(multi_buy_match.group(1))
                    total_price = float(multi_buy_match.group(2).replace(',', '.'))
                    price = total_price / quantity
                except Exception:
                    price = 0.0

        if price == 0.0:
            price_match = re.search(r'(\d+[\.,]\d{2})', price_text)
            if price_match:
                price = float(price_match.group(1).replace(',', '.'))
            else:
                price_match = re.search(r'(\d+)', price_text)
                price = float(price_match.group(1)) if price_match else 0.0

        # Extract original price if available
        original_price = price
        was_price_element = tile.select_one('.was-price, [class*="was-price"], [class*="original-price"]')
        if was_price_element:
            was_price_text = was_price_element.text.strip()
            original_price_match = re.search(r'(\d+[\.,]\d{2})', was_price_text)
            if original_price_match:
                original_price = float(original_price_match.group(1).replace(',', '.'))

        unit_element = tile.select_one('.product-tile__package-size, span[class*="product-tile__package-size"], .product-package-size')
        unit_text = unit_element.text.strip().lower() if unit_element else ""
        unit = "each"
        if "kg" in unit_text:
            unit = "kg"
        elif "lb" in unit_text:
            unit = "lb"

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
            "category": "Grocery"
        }

    async def _save_debug_info(self, page: Page, prefix: str):
        try:
            await page.screenshot(path=os.path.join(self.storage_path, f'{prefix}.png'))
            with open(os.path.join(self.storage_path, f'{prefix}.html'), 'w') as f:
                f.write(await page.content())
        except Exception:
            pass
