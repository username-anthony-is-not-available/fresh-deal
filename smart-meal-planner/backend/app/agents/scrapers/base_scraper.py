from abc import ABC, abstractmethod
import asyncio
import random
import os
from playwright.async_api import async_playwright, Playwright, Page

try:
    # playwright-stealth exposes helper functions, not a Stealth class.
    from playwright_stealth import stealth_async
except Exception:  # pragma: no cover
    stealth_async = None
from typing import List, Dict, Any, Optional
from app.core.proxy_manager import ProxyManager
from .user_agents import USER_AGENTS


class BaseScraper(ABC):
    """
    Abstract base class for all store-specific scrapers.
    Provides a common interface and shared functionalities for browser automation.
    """

    def __init__(
        self,
        headless: bool = True,
        proxy_manager: Optional[ProxyManager] = None,
        storage_path: str = "/tmp",
    ):
        self.headless = headless
        self.proxy_manager = proxy_manager or ProxyManager()
        self.storage_path = storage_path
        self.storage_state_path = os.path.join(
            storage_path, f"browser_storage_state_{self.__class__.__name__}.json"
        )
        self.user_agents = USER_AGENTS

    @abstractmethod
    async def _scrape_page(self, page: Page, limit: int) -> List[Dict[str, Any]]:
        """
        The main scraping logic to be implemented by each scraper subclass.
        This method receives a configured Page object.
        """
        pass

    async def scrape(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        The main method that handles browser setup, teardown, and proxy rotation.
        It calls the _scrape_page method where the actual scraping logic resides.
        """
        proxy = self.proxy_manager.get_proxy()

        async with async_playwright() as p:
            browser = None
            try:
                browser = await self._get_browser(p, proxy)
                context = await self._get_context(browser)
                page = await self._get_page(context)

                await self._simulate_mouse_movement(page)
                deals = await self._scrape_page(page, limit)
                await context.storage_state(path=self.storage_state_path)
                return deals
            except Exception as e:
                print(f"Scraping failed with proxy {proxy}: {e}")
                if proxy:
                    self.proxy_manager.blacklist_proxy(proxy)
                return []
            finally:
                if browser:
                    await browser.close()

    async def _get_browser(self, playwright: Playwright, proxy: Optional[str]):
        """
        Launches a new browser instance with randomized fingerprinting and proxy support.
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
        Creates a new browser context with a random user agent and other anti-detection measures.
        """
        user_agent = random.choice(self.user_agents)
        viewports = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1536, "height": 864},
            {"width": 1440, "height": 900},
            {"width": 1280, "height": 720},
        ]
        storage_state = (
            self.storage_state_path if os.path.exists(self.storage_state_path) else None
        )
        return await browser.new_context(
            user_agent=user_agent,
            viewport=random.choice(viewports),
            locale="en-CA",
            storage_state=storage_state,
        )

    async def _get_page(self, context):
        """
        Creates a new page and applies stealth measures to it.
        """
        page = await context.new_page()
        if stealth_async is not None:
            await stealth_async(page)
        return page

    async def _random_delay(self, min_delay: float = 1.0, max_delay: float = 3.0):
        """
        Waits for a random amount of time to mimic human behavior.
        """
        await asyncio.sleep(random.uniform(min_delay, max_delay))

    async def _simulate_mouse_movement(self, page: Page):
        """
        Simulates random mouse movements on the page.
        """
        viewport_size = page.viewport_size
        if viewport_size:
            width, height = viewport_size["width"], viewport_size["height"]
            for _ in range(10):
                await page.mouse.move(
                    random.uniform(0, width),
                    random.uniform(0, height),
                    steps=random.randint(1, 5),
                )
                await self._random_delay(0.1, 0.5)

    async def _type_with_random_delay(
        self,
        page: Page,
        selector: str,
        text: str,
        min_delay: float = 0.05,
        max_delay: float = 0.2,
    ):
        """
        Types text into an element with random delays between keystrokes.
        This is a utility method intended for subclasses that need to fill out forms.
        """
        for char in text:
            await page.type(selector, char)
            await self._random_delay(min_delay, max_delay)
