
from playwright.async_api import Page
from typing import List, Dict, Any
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import re
import logging

logger = logging.getLogger(__name__)

class WalmartScraper(BaseScraper):
    """
    Scraper for Walmart.ca. This scraper attempts to handle the flyer page.
    """
    STORE_NAME = "Walmart"

    async def _scrape_page(self, page: Page, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrapes the Walmart website for deals.
        """
        deals = []
        url = "https://www.walmart.ca/en/flyer"

        try:
            logger.info("Navigating to the Walmart flyer page.")
            await page.goto(url, wait_until="networkidle", timeout=120000)

            # Walmart's flyer is complex and may require scrolling to load all items
            for _ in range(5): # Scroll a few times to load more content
                await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                await self._random_delay(2, 4)


            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            flyer_items = soup.select('[data-testid="flyer-item"]')

            if not flyer_items:
                logger.warning("No flyer items found on the Walmart page. This could be due to anti-bot measures.")
                # Save debug information
                await page.screenshot(path='walmart_debug.png')
                with open('walmart_debug.html', 'w', encoding='utf-8') as f:
                    f.write(await page.content())
                return []

            for item in flyer_items:
                if len(deals) >= limit:
                    break

                try:
                    name_element = item.select_one('[data-testid="product-name"]')
                    price_element = item.select_one('[data-testid="price-deal"]')

                    if not name_element or not price_element:
                        continue

                    name = name_element.text.strip()
                    price_text = price_element.text.strip()

                    price_match = re.search(r'(\d+\.\d{2})', price_text.replace(',', '.'))
                    price = float(price_match.group(1)) if price_match else 0.0

                    unit = "each"
                    if "/lb" in price_text or "per lb" in price_text:
                        unit = "lb"
                    elif "/kg" in price_text or "per kg" in price_text:
                        unit = "kg"

                    deal = {
                        "name": name.strip(),
                        "price": price,
                        "original_price": price,
                        "unit": unit,
                        "store": self.STORE_NAME,
                        "category": "Flyer"
                    }
                    deals.append(deal)

                except Exception as e:
                    logger.error(f"Error scraping a Walmart flyer item: {e}")

        except Exception as e:
            logger.critical(f"A critical error occurred while scraping Walmart: {e}")
            await page.screenshot(path='walmart_critical_error.png')
            with open('walmart_critical_error.html', 'w', encoding='utf-8') as f:
                f.write(await page.content())


        logger.info(f"Scraped {len(deals)} deals from Walmart.")
        return deals
