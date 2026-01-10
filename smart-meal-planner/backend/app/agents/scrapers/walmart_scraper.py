
from playwright.async_api import Page
from typing import List, Dict, Any, Optional
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import logging
import re
from datetime import datetime, date
from dateutil.parser import parse

logger = logging.getLogger(__name__)

class WalmartScraper(BaseScraper):
    """
    A scraper for Walmart.ca flyer deals.
    This scraper uses Playwright to navigate the flyer page and extract deals.
    """
    STORE_NAME = "Walmart"

    def __init__(self, headless: bool = True, postal_code: str = "H4T1V6", proxy_manager: Optional[Any] = None, storage_path: str = "/tmp"):
        super().__init__(headless, proxy_manager, storage_path)
        self.postal_code = postal_code

    async def _scrape_page(self, page: Page, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrapes the Walmart.ca flyer page for deals.
        """
        deals = []
        url = "https://www.walmart.ca/en/flyer"
        logger.info(f"Navigating to {url} for {self.STORE_NAME} scraper.")

        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await self._handle_postal_code_modal(page)

            # Scroll to ensure all deals are loaded
            await self._scroll_to_bottom(page)

            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            valid_from, valid_until = self._parse_validity_dates(soup)

            deal_elements = soup.select('div[data-testid="flyer-item"]')
            logger.info(f"Found {len(deal_elements)} potential deals for {self.STORE_NAME}.")

            if not deal_elements:
                logger.warning(f"No deal elements found for {self.STORE_NAME}. Saving debug info.")
                await self._save_debug_info(page, "walmart_debug")
                return []

            for element in deal_elements:
                if len(deals) >= limit:
                    break

                deal = self._parse_deal_element(element, valid_from, valid_until)
                if deal:
                    deals.append(deal)

        except Exception as e:
            logger.critical(f"A critical error occurred while scraping {self.STORE_NAME}: {e}", exc_info=True)
            await self._save_debug_info(page, "walmart_critical_error")

        logger.info(f"Successfully scraped {len(deals)} deals from {self.STORE_NAME}.")
        return deals

    async def _handle_postal_code_modal(self, page: Page):
        """
        Handles the postal code modal that can appear on first visit.
        """
        modal_selector = 'div[class*="location-modal-content"]'
        input_selector = 'input[name="postal-code-input"]'

        try:
            # Wait for either the modal or the main content to be visible
            await page.wait_for_selector(f"{modal_selector}, div[data-automation='flyer-deal-item']", timeout=20000)

            if await page.is_visible(modal_selector):
                logger.info("Postal code modal detected. Entering postal code.")
                await self._type_with_random_delay(page, input_selector, self.postal_code)
                await page.press(input_selector, 'Enter')
                await page.wait_for_load_state("networkidle", timeout=30000)
                logger.info("Postal code submitted.")
        except Exception as e:
            logger.warning(f"Did not find or interact with the postal code modal, or it timed out: {e}")

    async def _scroll_to_bottom(self, page: Page):
        """
        Scrolls down the page to trigger lazy loading of more deals.
        """
        logger.info("Scrolling page to load all deals...")
        last_height = await page.evaluate("document.body.scrollHeight")
        for _ in range(5): # Limit scrolls to prevent infinite loops
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await self._random_delay(2, 4)
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                logger.info("Reached the bottom of the page.")
                break
            last_height = new_height
        logger.info("Finished scrolling.")

    def _parse_validity_dates(self, soup: BeautifulSoup) -> (Optional[date], Optional[date]):
        """
        Parses the flyer validity dates from the page soup, trying multiple regex patterns.
        """
        try:
            date_element = soup.select_one('div[data-testid="flyer-validity-dates"]')
            if not date_element:
                date_element = soup.select_one('div[data-testid="flyer-validity-dates"]')
            if not date_element:
                logger.warning("Could not find date element for parsing.")
                return None, None

            date_text = date_element.text.strip()

            # Pattern 1: End month is specified (e.g., "from Jan 30 to Feb 5, 2024")
            match = re.search(
                r'from\s+(?P<start_month>\w+)\s+(?P<start_day>\d+)\s+to\s+(?P<end_month>\w+)\s+(?P<end_day>\d+),\s+(?P<year>\d{4})',
                date_text,
                re.IGNORECASE
            )
            if match:
                start_str = f"{match.group('start_day')} {match.group('start_month')} {match.group('year')}"
                end_str = f"{match.group('end_day')} {match.group('end_month')} {match.group('year')}"
                valid_from = datetime.strptime(start_str, '%d %B %Y').date()
                valid_until = datetime.strptime(end_str, '%d %B %Y').date()
                return valid_from, valid_until

            # Pattern 2: End month is omitted (e.g., "from July 25 to 31, 2024")
            match = re.search(
                r'from\s+(?P<start_month>\w+)\s+(?P<start_day>\d+)\s+to\s+(?P<end_day>\d+),\s+(?P<year>\d{4})',
                date_text,
                re.IGNORECASE
            )
            if match:
                start_month = match.group('start_month')
                start_str = f"{match.group('start_day')} {start_month} {match.group('year')}"
                end_str = f"{match.group('end_day')} {start_month} {match.group('year')}"
                valid_from = datetime.strptime(start_str, '%d %B %Y').date()
                valid_until = datetime.strptime(end_str, '%d %B %Y').date()
                return valid_from, valid_until

            logger.warning(f"Could not match any date pattern for text: '{date_text}'")

        except Exception as e:
            logger.error(f"Error parsing validity dates: {e}")

        return None, None

    def _parse_deal_element(self, element: BeautifulSoup, valid_from: Optional[date], valid_until: Optional[date]) -> Optional[Dict[str, Any]]:
        """
        Parses a single deal element from the BeautifulSoup object.
        """
        try:
            name = element.select_one('div[data-testid="product-name"]').text.strip()
            price_text = element.select_one('div[data-testid="price-deal"]').text.strip()

            # Find the image, being flexible with the selector
            image_element = element.select_one('img')
            image_url = image_element['src'] if image_element and image_element.has_attr('src') else None

            # Enhanced price and unit extraction
            price_text = price_text.lower()
            unit = "each"
            price = 0.0

            multi_buy_match = re.search(r'(\d+)\s*for\s*\$?([\d,\.]+)', price_text)

            if multi_buy_match:
                quantity = int(multi_buy_match.group(1))
                total_price = float(multi_buy_match.group(2).replace(',', ''))
                price = round(total_price / quantity, 2)
            else:
                price_match = re.search(r'([\d,\.]+)', price_text)
                if price_match:
                    price = float(price_match.group(1).replace(',', ''))

            if "/lb" in price_text:
                unit = "lb"
            elif "/kg" in price_text:
                unit = "kg"

            return {
                "name": name,
                "price": price,
                "original_price": price, # Placeholder, not always available
                "unit": unit,
                "store": self.STORE_NAME,
                "image_url": image_url,
                "category": "Flyer",
                "valid_from": valid_from,
                "valid_until": valid_until
            }
        except (AttributeError, ValueError, TypeError) as e:
            logger.error(f"Error parsing deal element: {e} - Element: {element.prettify()}")
            return None

    async def _save_debug_info(self, page: Page, prefix: str):
        """
        Saves a screenshot and the HTML content for debugging purposes.
        """
        try:
            await page.screenshot(path=f'{prefix}.png')
            with open(f'{prefix}.html', 'w', encoding='utf-8') as f:
                f.write(await page.content())
            logger.info(f"Saved debug info with prefix: {prefix}")
        except Exception as e:
            logger.error(f"Failed to save debug info: {e}")
