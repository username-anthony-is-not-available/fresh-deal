
from playwright.async_api import Page
from typing import List, Dict, Any, Optional
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import re
import os
import logging

logger = logging.getLogger(__name__)

class IgaScraper(BaseScraper):
    """
    A functional scraper for IGA.net that handles the online flyer.
    """
    STORE_NAME = "IGA"

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

            # Handle the cookie consent button
            try:
                cookie_button_selector = 'button:has-text("Accept All")'
                if await page.is_visible(cookie_button_selector, timeout=10000):
                    await page.locator(cookie_button_selector).click()
                    logger.info("Successfully clicked the 'Accept All' cookie button.")
                    await page.wait_for_load_state("networkidle", timeout=20000)
            except Exception as e:
                logger.debug(f"Could not find or click the cookie button on IGA: {e}")

            # Wait for flyer content to load
            try:
                await page.wait_for_selector('div[class*="product-tile-wrapper"]', timeout=30000)
            except Exception as e:
                logger.warning(f"Timed out waiting for product tiles on IGA: {e}")
                # We'll continue anyway and try to parse what's there

            # Scroll to the bottom of the page to load all items
            last_height = await page.evaluate("document.body.scrollHeight")
            for _ in range(5): # Limit scrolling to avoid infinite loops
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                await self._random_delay(2, 4)
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            logger.info("Parsing the page content for deals.")
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            # Using a more specific selector to target flyer items
            product_tiles = soup.select('div[class*="product-tile-wrapper"]')

            if not product_tiles:
                logger.warning("No product tiles found on the IGA page.")
                debug_img = os.path.join(self.storage_path, 'iga_debug.png')
                debug_html = os.path.join(self.storage_path, 'iga_debug.html')
                await page.screenshot(path=debug_img)
                with open(debug_html, 'w', encoding='utf-8') as f:
                    f.write(await page.content())
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
            # Save a screenshot and HTML for debugging
            error_img = os.path.join(self.storage_path, 'iga_critical_error.png')
            error_html = os.path.join(self.storage_path, 'iga_critical_error.html')
            await page.screenshot(path=error_img)
            with open(error_html, 'w', encoding='utf-8') as f:
                f.write(await page.content())

        logger.info(f"Successfully scraped {len(deals)} deals from IGA.")
        return deals

    def _parse_tile(self, tile: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """
        Parses a single product tile for IGA.
        """
        name_element = tile.select_one('h3[class*="product-tile-name"]')
        price_element = tile.select_one('div[class*="product-tile-price"]')

        if not name_element or not price_element:
            return None

        name = name_element.text.strip()
        price_text = price_element.text.strip()

        # Handle price extraction
        price_match = re.search(r'(\d+[\.,]\d{2})', price_text)
        price = float(price_match.group(1).replace(',', '.')) if price_match else 0.0

        # Handle package size/unit
        unit_element = tile.select_one('div[class*="product-tile-package-size"]')
        unit_text = unit_element.text.strip().lower() if unit_element else ""

        unit = "each"
        if "kg" in unit_text:
            unit = "kg"
        elif "lb" in unit_text or "/lb" in name.lower():
            unit = "lb"

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
            "price": price,
            "original_price": price,
            "unit": unit,
            "store": self.STORE_NAME,
            "image_url": image_url,
            "category": "Grocery"
        }
