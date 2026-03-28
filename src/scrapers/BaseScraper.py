from abc import ABC, abstractmethod
import asyncio
import random
import os
import re
import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple
from playwright.async_api import async_playwright, Playwright, Page, BrowserContext
from bs4 import BeautifulSoup

try:
    from playwright_stealth import stealth_async
except ImportError:
    stealth_async = None

from src.core.proxy_manager import ProxyManager
from src.core.schema_validator import Deal

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """
    Abstract base class for all store-specific scrapers.
    Handles browser setup, anti-bot measures, and utility functions.
    """

    def __init__(
        self,
        postal_code: str = "H4T1V6",
        headless: bool = True,
        proxy_manager: Optional[ProxyManager] = None,
        storage_path: str = "/tmp/scrapers",
    ):
        self.postal_code = postal_code
        self.headless = headless
        self.proxy_manager = proxy_manager or ProxyManager()
        self.storage_path = storage_path
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path, exist_ok=True)

        self.last_screenshot: Optional[str] = None
        self.last_html: Optional[str] = None

    @abstractmethod
    async def fetch_deals(self, page: Page, limit: int) -> List[Deal]:
        """
        The main scraping logic to be implemented by each scraper subclass.
        This method receives a configured Page object.
        """
        pass

    @abstractmethod
    def parse_html(self, html_content: str) -> List[Deal]:
        """
        Static/HTML-based parsing logic (optional but encouraged).
        """
        pass

    async def scrape(self, limit: int = 50) -> List[Deal]:
        """
        Public entry point that handles browser lifecycle and error handling.
        """
        proxy = self.proxy_manager.get_proxy()

        async with async_playwright() as p:
            browser = None
            try:
                browser = await self._get_browser(p, proxy)
                context = await self._get_context(browser)
                page = await self._get_page(context)

                deals = await self.fetch_deals(page, limit)
                return deals

            except Exception as e:
                logger.error(f"Scraping failed: {e}")
                if 'page' in locals() and page:
                    self.last_screenshot, self.last_html = await self._save_debug_artifacts(page, self.__class__.__name__)
                raise e
            finally:
                if browser:
                    await browser.close()

    async def _get_browser(self, playwright: Playwright, proxy: Optional[str]):
        """
        Launches browser with optional proxy.
        """
        browser_args = ["--disable-blink-features=AutomationControlled"]
        proxy_config = None
        if proxy:
            proxy_config = {"server": proxy}

        return await playwright.chromium.launch(
            headless=self.headless, args=browser_args, proxy=proxy_config
        )

    async def _get_context(self, browser):
        """
        Creates context with randomized viewport.
        """
        user_agent = self.proxy_manager.get_user_agent()
        viewports = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1440, "height": 900},
        ]
        return await browser.new_context(
            user_agent=user_agent,
            viewport=random.choice(viewports),
            locale="en-CA",
        )

    async def _get_page(self, context: BrowserContext) -> Page:
        """
        Creates new page with stealth applied.
        """
        page = await context.new_page()
        if stealth_async:
            await stealth_async(page)
        return page

    async def _handle_cookie_consent(self, page: Page, selector: str, timeout: int = 5000) -> bool:
        """
        Clicks the cookie consent button if present.
        """
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            await page.click(selector)
            return True
        except Exception:
            return False

    async def _scroll_to_bottom(self, page: Page, max_scrolls: int = 5):
        """
        Scrolls down to load lazy content.
        """
        last_height = await page.evaluate("document.body.scrollHeight")
        for _ in range(max_scrolls):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(random.uniform(1.5, 3.0))
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    async def _save_debug_artifacts(self, page: Page, prefix: str) -> Tuple[str, str]:
        """
        Saves screenshot and HTML for debugging.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = os.path.join(self.storage_path, f"{prefix}_{timestamp}.png")
        html_path = os.path.join(self.storage_path, f"{prefix}_{timestamp}.html")

        await page.screenshot(path=screenshot_path)
        content = await page.content()
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(content)

        return screenshot_path, html_path

    def _parse_price(self, price_text: str) -> Optional[float]:
        """
        Basic price parsing from string.
        """
        if not price_text: return None
        # Simplified version of the one from app/agents/scrapers/base_scraper.py
        price_text = price_text.replace(",", ".").replace("$", "").strip()
        match = re.search(r"(\d+\.\d{2})", price_text)
        if match:
            return float(match.group(1))
        # Try integer
        match = re.search(r"(\d+)", price_text)
        if match:
            return float(match.group(1))
        return None

    def _extract_unit(self, text: str) -> str:
        """
        Extract unit from text (kg, lb, each, etc.)
        """
        text = text.lower()
        if "kg" in text or "/kg" in text: return "kg"
        if "lb" in text or "/lb" in text: return "lb"
        if "100g" in text or "/100g" in text: return "100g"
        return "each"
