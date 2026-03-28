import asyncio
import logging
from typing import List, Optional
from playwright.async_api import Page
from bs4 import BeautifulSoup
from src.scrapers.BaseScraper import BaseScraper
from src.core.schema_validator import Deal

logger = logging.getLogger(__name__)

class ProvigoScraper(BaseScraper):
    """
    Refactored Provigo Scraper using the new framework.
    """
    STORE_NAME = "Provigo"
    FLYER_URL = "https://www.provigo.ca/en/deals/flyer"

    async def fetch_deals(self, page: Page, limit: int = 50) -> List[Deal]:
        """
        Implementation of Provigo-specific fetching logic.
        """
        logger.info(f"Navigating to {self.FLYER_URL}")
        await page.goto(self.FLYER_URL, wait_until="domcontentloaded", timeout=60000)

        # Handle cookie consent
        await self._handle_cookie_consent(page, '#onetrust-accept-btn-handler')

        # Wait for loading spinner to disappear
        try:
            await page.wait_for_selector('div.loading--spinner', state='hidden', timeout=20000)
        except Exception:
            logger.debug("Spinner still visible or not found")

        # Wait for content to appear (native tiles)
        try:
            await page.wait_for_selector('[data-testid="product-title"]', timeout=20000)
        except Exception:
            logger.debug("Product titles not found, checking for Flipp iframe...")

        # Scroll to load more
        await self._scroll_to_bottom(page, max_scrolls=3)

        content = await page.content()
        deals = self.parse_html(content)
        if not deals:
            # Save artifacts if no deals found
            self.last_screenshot, self.last_html = await self._save_debug_artifacts(page, "Provigo_NoDeals")
            logger.warning(f"No deals found. Artifacts saved to {self.last_screenshot}")

        return deals[:limit]

    def parse_html(self, html_content: str) -> List[Deal]:
        """
        Implementation of Provigo-specific parsing logic using BeautifulSoup.
        """
        deals = []
        soup = BeautifulSoup(html_content, 'html.parser')

        # Native tiles
        product_tiles = soup.select('[data-testid="product-grid-component"]')
        if not product_tiles:
            # Try to find specific tile containers first
            product_tiles = soup.select('div[data-testid="product-tile"]')
        if not product_tiles:
            # Fallback for when data-testid is on a div that IS the tile (redundant but safe)
            product_tiles = soup.find_all('div', attrs={"data-testid": "product-tile"})
        if not product_tiles:
            product_tiles = soup.select('div[class*="product-tile"]:not([class*="package-size"])')

        logger.info(f"Found {len(product_tiles)} potential product tiles")

        for tile in product_tiles:
            try:
                name_el = tile.select_one('[data-testid="product-title"]') or tile.select_one('h3')
                if not name_el: continue
                name = name_el.get_text(strip=True)

                price_el = tile.select_one('[data-testid="price-product-tile"]') or tile.select_one('.price__value')
                if not price_el:
                    price_el = tile.select_one('[class*="price__value"]')
                if not price_el: continue
                price_text = price_el.get_text(separator=" ", strip=True)
                price = self._parse_price(price_text)

                if price is None: continue

                unit_el = tile.select_one('[data-testid="product-package-size"]')
                unit_text = unit_el.get_text(strip=True) if unit_el else ""
                unit = self._extract_unit(name + " " + unit_text)

                image_el = tile.select_one('img')
                image_url = image_el.get('src') if image_el else None

                deal = Deal(
                    name=name,
                    price=price,
                    unit=unit,
                    store=self.STORE_NAME,
                    image_url=image_url,
                    sale_info=price_text
                )
                deals.append(deal)
            except Exception as e:
                logger.error(f"Error parsing tile: {e}")

        return deals

if __name__ == "__main__":
    import sys
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Run a test scrape")
    args = parser.parse_args()

    if args.test:
        logging.basicConfig(level=logging.INFO)
        scraper = ProvigoScraper(headless=True)
        async def run():
            try:
                deals = await scraper.scrape(limit=10)
                print(json.dumps([d.model_dump() for d in deals], indent=2, default=str))
            except Exception as e:
                print(f"Scrape failed: {e}")
                if scraper.last_screenshot:
                    print(f"Artifacts: {scraper.last_screenshot}, {scraper.last_html}")
        asyncio.run(run())
