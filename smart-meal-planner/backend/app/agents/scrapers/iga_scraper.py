
from playwright.async_api import Page
from typing import List, Dict, Any
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import re
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
                await page.locator(cookie_button_selector).click(timeout=10000)
                logger.info("Successfully clicked the 'Accept All' cookie button.")
                await page.wait_for_load_state("networkidle", timeout=20000)
            except Exception as e:
                logger.warning(f"Could not find or click the cookie button: {e}")

            logger.info("Parsing the page content for deals.")
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            # Using a more specific selector to target flyer items
            product_tiles = soup.select('div[class*="product-tile-wrapper"]')

            if not product_tiles:
                logger.warning("No product tiles found on the page.")
                return []

            for tile in product_tiles:
                if len(deals) >= limit:
                    break

                try:
                    name = tile.select_one('h3[class*="product-tile-name"]').text.strip()
                    price_text = tile.select_one('div[class*="product-tile-price"]').text.strip()

                    price_match = re.search(r'(\d+[\.,]\d{2})', price_text)
                    price = float(price_match.group(1).replace(',', '.')) if price_match else 0.0

                    unit_text = (tile.select_one('div[class*="product-tile-package-size"]').text.strip().lower()
                                 if tile.select_one('div[class*="product-tile-package-size"]') else "")

                    unit = "each"
                    if "kg" in unit_text:
                        unit = "kg"
                    elif "lb" in unit_text or "/lb" in name.lower():
                        unit = "lb"

                    deal = {
                        "name": name,
                        "price": price,
                        "original_price": price,
                        "unit": unit,
                        "store": self.STORE_NAME,
                        "category": "Grocery"
                    }
                    deals.append(deal)

                except Exception as e:
                    logger.error(f"Error parsing a product tile: {e}")

        except Exception as e:
            logger.critical(f"A critical error occurred while scraping IGA: {e}")
            # Save a screenshot and HTML for debugging
            await page.screenshot(path='iga_critical_error.png')
            with open('iga_critical_error.html', 'w', encoding='utf-8') as f:
                f.write(await page.content())

        logger.info(f"Successfully scraped {len(deals)} deals from IGA.")
        return deals
