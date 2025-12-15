# WARNING: NON-FUNCTIONAL PLACEHOLDER
# The CSS selectors in this scraper are placeholders and are not guaranteed to work.
# They were written without access to the live website and must be verified and updated
# by a developer with browser access to the target site.
from playwright.async_api import Page
from typing import List, Dict, Any
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import re

class MetroScraper(BaseScraper):
    """
    Scraper for Metro.ca.
    """
    STORE_NAME = "Metro"

    async def _scrape_page(self, page: Page, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrapes the Metro website for deals.
        # WARNING: NON-FUNCTIONAL PLACEHOLDER
        # The CSS selectors in this scraper are placeholders and are not guaranteed to work.
        # They were written without access to the live website and must be verified and updated
        # by a developer with browser access to the target site.
        """
        deals = []
        categories = {
            "fruits-vegetables": "https://www.metro.ca/en/online-grocery/aisle/fruits-vegetables",
            "meat-poultry": "https://www.metro.ca/en/online-grocery/aisle/meat-poultry"
        }

        for category, url in categories.items():
            if len(deals) >= limit:
                break
            await page.goto(url, wait_until='domcontentloaded')
            try:
                # Handle the cookie consent banner first
                cookie_banner_button = await page.query_selector('#onetrust-accept-btn-handler')
                if cookie_banner_button:
                    await page.click('#onetrust-accept-btn-handler')
                    # Wait a bit for the banner to disappear and content to potentially load
                    await page.wait_for_timeout(2000)

                await page.wait_for_selector('.default-product-tile', timeout=20000)
            except Exception as e:
                print(f"Selector not found for Metro's {category} page. Saving debug info. Error: {e}")
                await page.screenshot(path=f'metro_debug_{category}.png')
                with open(f'metro_debug_{category}.html', 'w') as f:
                    f.write(await page.content())
                continue # Skip to the next category

            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            product_tiles = soup.select('.default-product-tile')
            for tile in product_tiles:
                if len(deals) >= limit:
                    break

                name = tile.select_one('.head__title').text.strip() if tile.select_one('.head__title') else 'Unknown Product'
                price_text = tile.select_one('.price-update').text.strip() if tile.select_one('.price-update') else '0'
                # Metro does not consistently show original price, so we'll use the current price as the original.
                original_price_text = price_text
                unit_text = tile.select_one('.unit-price').text.strip().lower() if tile.select_one('.unit-price') else ''

                price_match = re.search(r'\d+\.\d{2}', price_text.replace(',', '.'))
                price = float(price_match.group(0)) if price_match else 0.0

                original_price_match = re.search(r'\d+\.\d{2}', original_price_text.replace(',', '.'))
                original_price = float(original_price_match.group(0)) if original_price_match else price

                unit = "each"
                if "kg" in unit_text:
                    unit = "kg"
                elif "lb" in unit_text:
                    unit = "lb"

                deal = {
                    "name": name,
                    "price": price,
                    "original_price": original_price,
                    "unit": unit,
                    "store": self.STORE_NAME,
                    "category": category
                }
                deals.append(deal)

        return deals
