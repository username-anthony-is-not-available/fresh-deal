from playwright.async_api import Page
from typing import List, Dict, Any, Optional
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import re
import os
import logging
import asyncio

logger = logging.getLogger(__name__)

class MaxiScraper(BaseScraper):
    """
    Scraper for Maxi.ca. This scraper handles the flyer page,
    including location settings for Montreal and Flipp iframe integration.
    """
    STORE_NAME = "Maxi"

    def __init__(self, headless: bool = True, postal_code: str = "H2X 1Y1", proxy_manager: Optional[Any] = None, storage_path: str = "/tmp"):
        super().__init__(headless, proxy_manager, storage_path)
        self.postal_code = postal_code

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
                # Using domcontentloaded is safer for sites with lots of background tracking
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)

                # Check for bot detection
                content = await page.content()
                if "Incapsula incident ID" in content or "distil" in content.lower():
                    logger.warning(f"Bot detection triggered on {url}")
                    continue

                await asyncio.sleep(5)

                # Handle cookie consent
                await self._handle_cookie_consent(page)

                # Handle location setting
                await self._handle_location(page)

                # Scroll to load lazy content
                logger.info("Scrolling to load items...")
                for _ in range(3):
                    await page.keyboard.press("PageDown")
                    await asyncio.sleep(1)

                # Check for Flipp iframe
                flyer_frame_selector = 'iframe[title="Main Panel"]'
                flyer_frame = page.frame_locator(flyer_frame_selector)

                try:
                    frame_count = await flyer_frame.locator('[data-testid="product-tile"]').count()
                    if frame_count > 0:
                        logger.info(f"Found Flipp flyer frame with {frame_count} items.")
                        frame_content = await flyer_frame.locator('html').inner_html()
                        soup = BeautifulSoup(frame_content, 'html.parser')
                        tiles = soup.select('[data-testid="product-tile"]')
                        for tile in tiles:
                            deal = self._parse_tile(tile)
                            if deal and deal['name'] not in seen_names:
                                deals.append(deal)
                                seen_names.add(deal['name'])
                                if len(deals) >= limit:
                                    break
                except Exception as e:
                    logger.debug(f"Error checking Flipp frame: {e}")

                # Also check native content
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')

                # Find all potential product titles
                titles = soup.select('[data-testid="product-title"]')
                logger.info(f"Found {len(titles)} potential native titles on {url}")

                for title_elem in titles:
                    if len(deals) >= limit:
                        break

                    # Find the closest container: 'chakra-linkbox' or parent with price
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
            await self._save_debug_info(page, "maxi_failed_all")

        logger.info(f"Scraped total of {len(deals)} unique deals from {self.STORE_NAME}.")
        return deals

    async def _handle_cookie_consent(self, page: Page):
        try:
            selector = '#onetrust-accept-btn-handler'
            if await page.is_visible(selector, timeout=3000):
                await page.click(selector)
                await asyncio.sleep(1)
        except Exception:
            pass

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
        if not price_element:
            return None

        # Use get_text with separator to avoid merging joined lines
        price_text = price_element.get_text(separator=" ", strip=True)
        # Clean price text
        price_text = re.sub(r'(?i)sale|member price|limit \d+.*', '', price_text).strip()

        price = 0.0
        if "for" in price_text.lower() or "/" in price_text:
            multi_buy_match = re.search(r'(\d+)\s*(?:for|/)\s*[\$]?\s*(\d+[\.,]\d{2})', price_text.lower())
            if multi_buy_match:
                try:
                    quantity = int(multi_buy_match.group(1))
                    total_price = float(multi_buy_match.group(2).replace(',', '.'))
                    price = total_price / quantity
                except Exception:
                    price = 0.0

        if price == 0.0:
            price_match = re.search(r'(\d+[\.,]\d{2})', price_text)
            if price_match:
                price = float(price_match.group(1).replace(',', '.'))
            else:
                price_match = re.search(r'(\d+)', price_text)
                price = float(price_match.group(1)) if price_match else 0.0

        if price == 0.0:
            return None

        # Original Price
        original_price = price
        was_price_element = tile.select_one('[data-testid="was-price"]') or tile.select_one('.was-price')
        if was_price_element:
            was_price_text = was_price_element.get_text(strip=True)
            original_price_match = re.search(r'(\d+[\.,]\d{2})', was_price_text)
            if original_price_match:
                original_price = float(original_price_match.group(1).replace(',', '.'))

        # Unit/Size
        unit_element = tile.select_one('[data-testid="product-package-size"]') or tile.select_one('.product-tile__package-size')
        unit_text = unit_element.get_text(strip=True).lower() if unit_element else ""
        unit = "each"
        if "kg" in unit_text:
            unit = "kg"
        elif "lb" in unit_text:
            unit = "lb"
        elif "g" in unit_text and "100g" not in unit_text:
            unit = "g"

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
            "category": "Grocery"
        }

    async def _save_debug_info(self, page: Page, prefix: str):
        try:
            await page.screenshot(path=os.path.join(self.storage_path, f'{prefix}.png'))
            with open(os.path.join(self.storage_path, f'{prefix}.html'), 'w') as f:
                f.write(await page.content())
        except Exception:
            pass
