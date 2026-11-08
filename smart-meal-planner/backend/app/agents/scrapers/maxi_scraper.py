from app.core.config import settings
from playwright.async_api import Page
from typing import List, Dict, Any, Optional
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import re
import logging
import asyncio

logger = logging.getLogger(__name__)

class MaxiScraper(BaseScraper):
    """
    Scraper for Maxi.ca. This scraper handles the flyer page,
    including location settings for Montreal and Flipp iframe integration.
    """
    STORE_NAME = "Maxi"

    def __init__(self, postal_code: Optional[str] = None, headless: bool = True, proxy_manager: Optional[Any] = None, storage_path: str = "/tmp"):
        postal_code = postal_code or getattr(settings, "LOCAL_POSTAL_CODE", None) or settings.DEFAULT_POSTAL_CODE
        super().__init__(postal_code, headless, proxy_manager, storage_path)

    async def _scrape_page(self, page: Page, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrapes the Maxi website for deals.
        """
        deals = []
        urls = [
            "https://www.maxi.ca/en/deals/flyer",
            "https://www.maxi.ca/en/flyer",
            "https://www.maxi.ca/en/collection/deals-centre"
        ]

        seen_names = set()

        for url in urls:
            if len(deals) >= limit:
                break

            try:
                logger.info(f"Navigating to {self.STORE_NAME} URL: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)

                # Check for bot detection
                if await self._check_incapsula_block(page):
                    logger.warning(f"Bot detection triggered on {url}")
                    continue

                await asyncio.sleep(5)

                # Handle cookie consent
                await self._handle_cookie_consent(page, '#onetrust-accept-btn-handler')

                # Handle location setting
                await self._handle_location(page)

                # Scroll to load lazy content
                logger.info("Scrolling to load items...")
                await self._scroll_to_bottom(page, max_scrolls=3)

                # Check for Flipp iframe
                tiles = await self._scrape_flipp_frame(page)
                for tile in tiles:
                    deal = self._parse_tile(tile)
                    if deal and deal['name'] not in seen_names:
                        deals.append(deal)
                        seen_names.add(deal['name'])
                        if len(deals) >= limit:
                            break

                # Also check native content
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')

                # Find all potential product titles
                titles = soup.select('[data-testid="product-title"]')
                logger.info(f"Found {len(titles)} potential native titles on {url}")

                for title_elem in titles:
                    if len(deals) >= limit:
                        break

                    # Find the closest container
                    container = title_elem.find_parent('div', class_=lambda x: x and 'chakra-linkbox' in x)
                    if not container:
                        curr = title_elem
                        for _ in range(5):
                            curr = curr.parent
                            if not curr:
                                break
                            if curr.select_one('[data-testid="sale-price"], [data-testid="regular-price"], [data-testid="price-product-tile"]'):
                                container = curr
                                break

                    if container:
                        deal = self._parse_tile(container)
                        if deal and deal['name'] not in seen_names:
                            deals.append(deal)
                            seen_names.add(deal['name'])

                if deals:
                    logger.info(f"Currently have {len(deals)} deals after scraping {url}")

            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                continue

        if not deals:
            await self._save_debug_artifacts(page, "maxi_failed_all")

        logger.info(f"Scraped total of {len(deals)} unique deals from {self.STORE_NAME}.")
        return deals

    async def _handle_location(self, page: Page):
        """
        Attempts to set the location to Montreal.
        """
        try:
            content = await page.content()
            if self.postal_code in content or "H2X 1Y1" in content:
                return

            picker_selectors = [
                'button[data-testid="iceberg-fulfillment-trigger"]',
                'button[aria-label*="location"]',
                'button[aria-label*="store"]',
                'button:has-text("Store")'
            ]

            for sel in picker_selectors:
                if await page.is_visible(sel, timeout=3000):
                    logger.info("Opening location picker")
                    await page.click(sel)
                    await asyncio.sleep(2)
                    break

            input_sel = 'input[id="location-search"], input[data-testid="location-search"], input[placeholder*="Postal"]'
            if await page.is_visible(input_sel, timeout=5000):
                await page.fill(input_sel, self.postal_code)
                await page.keyboard.press("Enter")
                await asyncio.sleep(3)

                set_store_btns = [
                    'button:has-text("Set as my store")',
                    'button:has-text("Select")',
                    'button[data-testid="select-store-button"]'
                ]
                for btn in set_store_btns:
                    if await page.is_visible(btn, timeout=3000):
                        await page.click(btn)
                        await asyncio.sleep(2)
                        logger.info(f"Set location for {self.STORE_NAME}")
                        return
        except Exception as e:
            logger.warning(f"Failed to set location for {self.STORE_NAME}: {e}")

    def _parse_tile(self, tile: BeautifulSoup) -> Optional[Dict[str, Any]]:
        # Extract Name
        name_element = (
            tile.select_one('[data-testid="product-title"]') or
            tile.select_one('h3') or
            tile.select_one('.product-name')
        )
        if not name_element:
            return None

        name = name_element.get_text(strip=True)
        if name.lower().startswith("add "):
            name = name[4:].replace(" to cart", "").strip()

        brand_element = tile.select_one('[data-testid="product-brand"]')
        if brand_element:
            brand = brand_element.get_text(strip=True)
            if brand and brand.lower() not in name.lower():
                name = f"{brand} {name}"

        # Extract Price
        price_element = (
            tile.select_one('[data-testid="sale-price"]') or
            tile.select_one('[data-testid="regular-price"]') or
            tile.select_one('[data-testid="price-product-tile"]') or
            tile.select_one('.price__value')
        )

        price = 0.0
        if price_element:
            price_text = price_element.get_text(separator=" ", strip=True)
            price_text = re.sub(r'(?i)sale|member price|limit \d+.*', '', price_text).strip()
            price = self._parse_price(price_text) or 0.0

        if price == 0.0:
            return None

        # Original Price
        original_price = price
        was_price_element = tile.select_one('[data-testid="was-price"]') or tile.select_one('.was-price')
        if was_price_element:
            was_price_text = was_price_element.get_text(strip=True)
            original_price = self._parse_price(was_price_text) or price

        # Unit/Size
        unit_element = tile.select_one('[data-testid="product-package-size"]') or tile.select_one('.product-tile__package-size')
        unit_text = unit_element.get_text(strip=True).lower() if unit_element else ""

        price_text_for_unit = price_element.get_text(strip=True).lower() if price_element else ""
        unit = self._extract_unit(name + " " + unit_text + " " + price_text_for_unit)

        # Loyalty Info
        loyalty_info = self._parse_loyalty_points(tile.get_text(separator=" "))
        loyalty_program, loyalty_points = loyalty_info if loyalty_info else (None, None)

        # Image URL
        image_element = tile.select_one('[data-testid="product-image"] img') or tile.select_one('img')
        image_url = None
        if image_element:
            image_url = image_element.get('src') or image_element.get('data-src') or image_element.get('srcset')
            if image_url and image_url.startswith('data:'):
                image_url = image_element.get('data-src') or image_url

        return {
            "name": name,
            "price": round(price, 2),
            "original_price": round(original_price, 2),
            "unit": unit,
            "store": self.STORE_NAME,
            "image_url": image_url,
            "category": self._categorize_product(name),
            "loyalty_program": loyalty_program,
            "loyalty_points": loyalty_points,
            "sale_info": price_element.get_text(separator=" ", strip=True) if price_element else None
        }
