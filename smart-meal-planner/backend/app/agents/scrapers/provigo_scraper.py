
from playwright.async_api import Page
from typing import List, Dict, Any, Optional
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import re
import os
import logging

logger = logging.getLogger(__name__)

class ProvigoScraper(BaseScraper):
    """
    Scraper for Provigo.ca. This scraper is designed to handle the flyer page,
    including the Flipp iframe integration.
    """
    STORE_NAME = "Provigo"

    async def _scrape_page(self, page: Page, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrapes the Provigo website for deals.
        """
        deals = []
        url = "https://www.provigo.ca/en/flyer"

        try:
            logger.info("Navigating to the Provigo flyer page.")
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Handle cookie consent if it appears
            try:
                cookie_button_selector = '#onetrust-accept-btn-handler'
                if await page.is_visible(cookie_button_selector, timeout=5000):
                    await page.locator(cookie_button_selector).click()
                    logger.info("Accepted cookie consent on Provigo.")
                    await page.wait_for_load_state("networkidle", timeout=20000)
            except Exception as e:
                logger.debug(f"Could not find or click the cookie button on Provigo: {e}")

            # Try to find the Flipp iframe
            flyer_frame = page.frame_locator('iframe[title="Main Panel"]')

            # Check if we can find product tiles within the frame
            try:
                # Wait for the tiles to appear in the frame
                tile_locator = flyer_frame.locator('div[data-testid="product-tile"]')
                await tile_locator.first.wait_for(timeout=20000)
                logger.info("Found Flipp flyer frame on Provigo.")

                # Get the HTML from the frame
                frame_content = await flyer_frame.locator('html').inner_html()
                soup = BeautifulSoup(frame_content, 'html.parser')
                product_tiles = soup.select('div[data-testid="product-tile"]')
            except Exception as e:
                logger.info(f"Flipp flyer frame not found or timed out ({e}), falling back to main page content.")
                # Fallback to main page content
                await page.wait_for_selector('div[class*="product-tile-group__list__item"]', timeout=20000)
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                product_tiles = soup.select('div[class*="product-tile-group__list__item"]')

            logger.info(f"Found {len(product_tiles)} product tiles on Provigo.")

            if not product_tiles:
                logger.warning("No product tiles found on the Provigo page. This could be due to anti-bot measures.")
                debug_img = os.path.join(self.storage_path, 'provigo_debug.png')
                debug_html = os.path.join(self.storage_path, 'provigo_debug.html')
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
                    logger.error(f"Error parsing a Provigo product tile: {e}")

        except Exception as e:
            logger.critical(f"A critical error occurred while scraping Provigo: {e}")
            error_img = os.path.join(self.storage_path, 'provigo_critical_error.png')
            error_html = os.path.join(self.storage_path, 'provigo_critical_error.html')
            await page.screenshot(path=error_img)
            with open(error_html, 'w', encoding='utf-8') as f:
                f.write(await page.content())

        logger.info(f"Scraped {len(deals)} deals from Provigo.")
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
        name = name_element.text.strip()

        # 2. Extract Price
        price_element = tile.select_one('.price__value') # Both Flipp and Native often use this
        if not price_element:
            price_element = tile.select_one('span[class*="price__value"]')

        if not price_element:
            return None
        price_text = price_element.text.strip()

        # Prices can be in formats like "2/5.00" or "5.99"
        if "/" in price_text:
            parts = price_text.split("/")
            try:
                price = float(parts[1]) / int(parts[0])
            except (ValueError, ZeroDivisionError):
                price = 0.0
        else:
            price_match = re.search(r'(\d+[\.,]\d{2})', price_text)
            if price_match:
                price = float(price_match.group(1).replace(',', '.'))
            else:
                # Try a simpler regex if the above fails
                price_match = re.search(r'(\d+)', price_text)
                price = float(price_match.group(1)) if price_match else 0.0

        # 3. Extract Unit/Package Size
        unit_element = tile.select_one('.product-tile__package-size') # Flipp
        if not unit_element:
            unit_element = tile.select_one('div.product-tile__package-size')
        if not unit_element:
            unit_element = tile.select_one('span[class*="product-tile__package-size"]') # Native

        unit_text = unit_element.text.strip().lower() if unit_element else ""
        unit = "each"
        if "kg" in unit_text:
            unit = "kg"
        elif "lb" in unit_text:
            unit = "lb"

        # 4. Extract Image
        image_element = tile.select_one('img')
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
            "category": "Grocery"
        }
