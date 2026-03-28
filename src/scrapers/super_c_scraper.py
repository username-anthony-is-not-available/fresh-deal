import asyncio
import logging
from typing import List, Optional
from playwright.async_api import Page
from bs4 import BeautifulSoup
from src.scrapers.BaseScraper import BaseScraper
from src.core.schema_validator import Deal

logger = logging.getLogger(__name__)

class SuperCScraper(BaseScraper):
    """
    Scraper for SuperC.ca flyer using the new framework.
    Handles Flipp iframe and native fallback.
    """
    STORE_NAME = "Super C"
    FLYER_URL = "https://www.superc.ca/en/flyer"

    async def fetch_deals(self, page: Page, limit: int = 50) -> List[Deal]:
        """
        Implementation of Super C specific fetching logic.
        """
        try:
            logger.info(f"Navigating to {self.STORE_NAME} flyer page: {self.FLYER_URL}")
            await page.goto(self.FLYER_URL, wait_until="networkidle", timeout=60000)
            await self._random_delay(2, 5)

            if await self._check_incapsula_block(page):
                logger.critical(f"{self.STORE_NAME} access denied by Incapsula.")
                return []

            await self._handle_cookie_consent(page, '#onetrust-accept-btn-handler')

            # 1. Try Flipp Frame
            tiles = await self._scrape_flipp_frame(page)
            if tiles:
                logger.info(f"Found {len(tiles)} tiles in Flipp iframe for {self.STORE_NAME}")
                deals = []
                for tile in tiles:
                    if len(deals) >= limit: break
                    deal = self._parse_tile(tile)
                    if deal: deals.append(deal)
                return deals

            # 2. Fallback to native tiles
            logger.info(f"Flipp frame not found or empty on {self.STORE_NAME}, looking for native tiles.")
            try:
                await page.wait_for_selector('div[class*="product-tile"]', timeout=10000)
                await self._scroll_to_bottom(page, max_scrolls=3)
                content = await page.content()
                return self.parse_html(content)[:limit]
            except Exception:
                logger.warning(f"No native tiles found on {self.STORE_NAME}.")

        except Exception as e:
            logger.error(f"Error scraping {self.STORE_NAME}: {e}")
            self.last_screenshot, self.last_html = await self._save_debug_artifacts(page, f"{self.STORE_NAME}_error")

        return []

    def parse_html(self, html_content: str) -> List[Deal]:
        """
        Static/HTML-based parsing for native tiles.
        """
        deals = []
        soup = BeautifulSoup(html_content, 'html.parser')
        product_tiles = soup.select('div[class*="product-tile"]')

        for tile in product_tiles:
            deal = self._parse_tile(tile)
            if deal: deals.append(deal)

        return deals

    def _parse_tile(self, tile: BeautifulSoup) -> Optional[Deal]:
        """
        Parses a single tile, supporting both Flipp and native selectors.
        """
        try:
            # 1. Extract Name
            name_element = tile.select_one('[data-testid="product-title"]') # Flipp
            if not name_element:
                name_element = tile.select_one('h3[class*="product-tile__name"]') # Native

            if not name_element: return None
            name = name_element.get_text(strip=True)

            # 2. Extract Price
            price_element = tile.select_one('.price__value')
            if not price_element:
                price_element = tile.select_one('span[class*="price__value"]')
            if not price_element:
                price_element = tile.select_one('[data-testid="sale-price"]')

            if not price_element: return None
            price_text = price_element.get_text(strip=True)
            price = self._parse_price(price_text)
            if price is None: return None

            # 3. Extract Unit
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

            return Deal(
                name=name,
                price=price,
                unit=unit,
                store=self.STORE_NAME,
                category=self._categorize_product(name),
                image_url=image_url,
                sale_info=price_text
            )
        except Exception as e:
            logger.error(f"Error parsing Super C tile: {e}")
            return None

if __name__ == "__main__":
    import sys
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Run a test scrape")
    args = parser.parse_args()

    if args.test:
        logging.basicConfig(level=logging.INFO)
        scraper = SuperCScraper(headless=True)
        async def run():
            try:
                deals = await scraper.scrape(limit=10)
                print(json.dumps([d.model_dump() for d in deals], indent=2, default=str))
            except Exception as e:
                print(f"Scrape failed: {e}")
                if scraper.last_screenshot:
                    print(f"Artifacts: {scraper.last_screenshot}, {scraper.last_html}")
        asyncio.run(run())
