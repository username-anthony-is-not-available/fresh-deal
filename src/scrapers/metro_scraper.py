import asyncio
import logging
from typing import List
from playwright.async_api import Page
from bs4 import BeautifulSoup
from src.scrapers.BaseScraper import BaseScraper
from src.core.schema_validator import Deal

logger = logging.getLogger(__name__)

class MetroScraper(BaseScraper):
    """
    Scraper for Metro.ca flyer using the new framework.
    """
    STORE_NAME = "Metro"
    FLYER_URLS = [
        "https://www.metro.ca/en/online-grocery/flyer",
        "https://www.metro.ca/en/flyer"
    ]

    async def fetch_deals(self, page: Page, limit: int = 50) -> List[Deal]:
        """
        Implementation of Metro-specific fetching logic.
        """
        deals = []
        for url in self.FLYER_URLS:
            if len(deals) >= limit:
                break
            try:
                logger.info(f"Navigating to Metro flyer page: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(5)

                if await self._check_incapsula_block(page):
                    logger.warning(f"Bot detection triggered on {url}")
                    continue

                await self._handle_cookie_consent(page, '#onetrust-accept-btn-handler')

                try:
                    await self._scroll_to_bottom(page, max_scrolls=3)
                except Exception as e:
                    logger.warning(f"Error while scrolling Metro: {e}")

                content = await page.content()
                new_deals = self.parse_html(content)
                for d in new_deals:
                    if len(deals) >= limit:
                        break
                    if not any(existing.name == d.name for existing in deals):
                        deals.append(d)

            except Exception as e:
                logger.error(f"Error scraping Metro URL {url}: {e}")
                continue

        if not deals:
            self.last_screenshot, self.last_html = await self._save_debug_artifacts(page, "Metro_NoDeals")
            logger.warning("No deals found on Metro. Artifacts saved.")

        return deals[:limit]

    def parse_html(self, html_content: str) -> List[Deal]:
        """
        Implementation of Metro-specific parsing logic using BeautifulSoup.
        """
        deals = []
        soup = BeautifulSoup(html_content, 'html.parser')

        product_tiles = soup.select('div.default-product-tile.tile-product')
        if not product_tiles:
            product_tiles = soup.select('div.product-tile-group__list__item')

        logger.info(f"Found {len(product_tiles)} potential product tiles on Metro")

        for tile in product_tiles:
            try:
                # 1. Extract Name
                name_element = tile.select_one('span.head__title')
                if not name_element:
                    name_element = tile.select_one('h3[class*="product-tile__name"]')

                name = ""
                if not name_element:
                    name = tile.get('data-product-name', "")
                else:
                    name = name_element.get_text(strip=True)

                if not name:
                    continue

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

                if not price_element:
                    continue
                price_text = price_element.get_text(strip=True)
                price = self._parse_price(price_text)

                if price is None:
                    continue

                # 4. Extract Original Price
                original_price = price
                regular_price_element = tile.select_one('div.pricing__before-price')
                if regular_price_element:
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

                deal = Deal(
                    name=name,
                    price=price,
                    original_price=original_price,
                    unit=unit,
                    store=self.STORE_NAME,
                    category=self._categorize_product(name),
                    image_url=image_url,
                    sale_info=price_text
                )
                deals.append(deal)
            except Exception as e:
                logger.error(f"Error parsing Metro tile: {e}")

        return deals

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Run a test scrape")
    args = parser.parse_args()

    if args.test:
        logging.basicConfig(level=logging.INFO)
        scraper = MetroScraper(headless=True)
        async def run():
            try:
                deals = await scraper.scrape(limit=10)
                print(json.dumps([d.model_dump() for d in deals], indent=2, default=str))
            except Exception as e:
                print(f"Scrape failed: {e}")
                if scraper.last_screenshot:
                    print(f"Artifacts: {scraper.last_screenshot}, {scraper.last_html}")
        asyncio.run(run())
