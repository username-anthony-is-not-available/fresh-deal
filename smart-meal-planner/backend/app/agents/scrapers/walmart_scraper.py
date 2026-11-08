from app.core.config import settings

from playwright.async_api import Page
from typing import List, Dict, Any, Optional
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import logging
from datetime import date

logger = logging.getLogger(__name__)

class WalmartScraper(BaseScraper):
    """
    A scraper for Walmart.ca flyer deals.
    This scraper uses Playwright to navigate the flyer page and extract deals.
    """
    STORE_NAME = "Walmart"

    def __init__(self, postal_code: Optional[str] = None, headless: bool = True, proxy_manager: Optional[Any] = None, storage_path: str = "/tmp"):
        postal_code = postal_code or getattr(settings, "LOCAL_POSTAL_CODE", None) or settings.DEFAULT_POSTAL_CODE
        super().__init__(postal_code, headless, proxy_manager, storage_path)

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
            await self._scroll_to_bottom(page, max_scrolls=5)

            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            date_element = soup.select_one('div[data-testid="flyer-validity-dates"]')
            valid_from, valid_until = (None, None)
            if date_element:
                valid_from, valid_until = self._parse_flyer_dates(date_element.text)

            deal_elements = soup.select('div[data-testid="flyer-item"]')
            logger.info(f"Found {len(deal_elements)} potential deals for {self.STORE_NAME}.")

            if not deal_elements:
                logger.warning(f"No deal elements found for {self.STORE_NAME}. Saving debug info.")
                await self._save_debug_artifacts(page, "walmart_debug")
                return []

            for element in deal_elements:
                if len(deals) >= limit:
                    break

                deal = self._parse_deal_element(element, valid_from, valid_until)
                if deal:
                    # Apply categorization
                    deal["category"] = self._categorize_product(deal["name"])
                    deals.append(deal)

        except Exception as e:
            logger.critical(f"A critical error occurred while scraping {self.STORE_NAME}: {e}", exc_info=True)
            await self._save_debug_artifacts(page, "walmart_critical_error")

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

    def _parse_deal_element(self, element: BeautifulSoup, valid_from: Optional[date], valid_until: Optional[date]) -> Optional[Dict[str, Any]]:
        """
        Parses a single deal element from the BeautifulSoup object.
        """
        try:
            name_el = element.select_one('div[data-testid="product-name"]')
            if not name_el:
                return None
            name = name_el.text.strip()

            price_element = element.select_one('div[data-testid="price-deal"]')

            price = 0.0
            unit = "each"

            if price_element:
                price_text = price_element.text.strip()
                price = self._parse_price(price_text) or 0.0
                unit = self._extract_unit(name + " " + price_text)

            if price == 0.0:
                return None

            # Find the image, being flexible with the selector
            image_element = element.select_one('img')
            image_url = image_element['src'] if image_element and image_element.has_attr('src') else None

            return {
                "name": name,
                "price": round(price, 2),
                "original_price": round(price, 2), # Placeholder, not always available
                "unit": unit,
                "store": self.STORE_NAME,
                "image_url": image_url,
                "category": "Flyer", # Will be overridden in _scrape_page
                "valid_from": valid_from,
                "valid_until": valid_until,
                "sale_info": price_element.text.strip() if price_element else None
            }
        except (AttributeError, ValueError, TypeError) as e:
            logger.error(f"Error parsing deal element: {e}")
            return None
