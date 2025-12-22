
from playwright.async_api import Page
from typing import List, Dict, Any
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import re
import logging

logger = logging.getLogger(__name__)

class ProvigoScraper(BaseScraper):
    """
    Scraper for Provigo.ca. This scraper is designed to handle the flyer page,
    which is a client-side rendered application.
    """
    STORE_NAME = "Provigo"

    async def _scrape_page(self, page: Page, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrapes the Provigo flyer website for deals.
        """
        deals = []
        url = "https://www.provigo.ca/en/flyer"

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            cookie_button_selector = 'button:has-text("Accept All")'
            try:
                await page.locator(cookie_button_selector).click(timeout=15000)
                logger.info("Accepted cookie consent.")
                await page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                logger.warning("Cookie consent button not found or failed to click. Proceeding...")

            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            product_tiles = soup.select('[data-testid="product-tile"]')
            logger.info(f"Found {len(product_tiles)} product tiles.")

            for tile in product_tiles:
                if len(deals) >= limit:
                    break

                try:
                    name_element = tile.select_one('[data-testid="product-title"]')
                    name = name_element.text.strip() if name_element else "Unknown Product"

                    price_element = tile.select_one('.price__value')
                    price_text = price_element.text.strip() if price_element else "0"

                    price_match = re.search(r'(\d+\.\d{2})', price_text.replace(',', '.'))
                    price = float(price_match.group(1)) if price_match else 0.0

                    unit_element = tile.select_one('.product-tile__package-size')
                    unit_text = unit_element.text.strip().lower() if unit_element else ""

                    unit = "each"
                    if "kg" in unit_text:
                        unit = "kg"
                    elif "lb" in unit_text or "/lb" in name:
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
            logger.critical(f"A critical error occurred while scraping Provigo: {e}")

        return deals
