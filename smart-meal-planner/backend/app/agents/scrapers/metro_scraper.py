
from playwright.async_api import Page
from typing import List, Dict, Any
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import re
import logging

logger = logging.getLogger(__name__)

class MetroScraper(BaseScraper):
    """
    Scraper for Metro.ca. This scraper is designed to handle the flyer page.
    """
    STORE_NAME = "Metro"

    async def _scrape_page(self, page: Page, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrapes the Metro website for deals.
        """
        deals = []
        url = "https://www.metro.ca/en/online-grocery/flyer"

        try:
            logger.info("Navigating to the Metro flyer page.")
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Handle cookie consent
            try:
                cookie_button_selector = '#onetrust-accept-btn-handler'
                await page.locator(cookie_button_selector).click(timeout=10000)
                logger.info("Accepted cookie consent on Metro.")
                await page.wait_for_load_state("networkidle", timeout=20000)
            except Exception as e:
                logger.warning(f"Could not find or click the cookie button on Metro: {e}")

            # Scroll to load more products
            last_height = await page.evaluate("document.body.scrollHeight")
            while True:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await self._random_delay(2, 4)
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            product_tiles = soup.select('div[class*="product-tile-group__list__item"]')
            logger.info(f"Found {len(product_tiles)} product tiles on Metro.")

            if not product_tiles:
                logger.warning("No product tiles found on the Metro page. This could be due to anti-bot measures.")
                await page.screenshot(path='metro_debug.png')
                with open('metro_debug.html', 'w', encoding='utf-8') as f:
                    f.write(await page.content())
                return []

            for tile in product_tiles:
                if len(deals) >= limit:
                    break

                try:
                    name_element = tile.select_one('h3[class*="product-tile__name"]')
                    price_element = tile.select_one('span[class*="price__value"]')
                    image_element = tile.select_one('img[class*="product-tile__image__image"]')

                    if not name_element or not price_element:
                        continue

                    name = name_element.text.strip()
                    price_text = price_element.text.strip()
                    image_url = image_element['src'] if image_element and image_element.has_attr('src') else None

                    price_match = re.search(r'(\d+\.\d{2})', price_text.replace(',', '.'))
                    price = float(price_match.group(1)) if price_match else 0.0

                    unit_element = tile.select_one('span[class*="product-tile__package-size"]')
                    unit_text = unit_element.text.strip().lower() if unit_element else ""

                    unit = "each"
                    if "kg" in unit_text:
                        unit = "kg"
                    elif "lb" in unit_text:
                        unit = "lb"

                    deal = {
                        "name": name,
                        "price": price,
                        "original_price": price,
                        "unit": unit,
                        "store": self.STORE_NAME,
                        "image_url": image_url,
                        "category": "Grocery"
                    }
                    deals.append(deal)
                except Exception as e:
                    logger.error(f"Error parsing a Metro product tile: {e}")

        except Exception as e:
            logger.critical(f"A critical error occurred while scraping Metro: {e}")
            await page.screenshot(path='metro_critical_error.png')
            with open('metro_critical_error.html', 'w', encoding='utf-8') as f:
                f.write(await page.content())

        logger.info(f"Scraped {len(deals)} deals from Metro.")
        return deals
