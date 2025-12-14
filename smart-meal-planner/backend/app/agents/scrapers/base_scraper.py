from abc import ABC, abstractmethod
import asyncio
import random
from playwright.async_api import async_playwright
from typing import List, Dict, Any, Optional

class BaseScraper(ABC):
    """
    Abstract base class for all store-specific scrapers.
    Provides a common interface and shared functionalities for browser automation.
    """

    def __init__(self, headless: bool = True, proxy: Optional[str] = None):
        self.headless = headless
        self.proxy = proxy
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
        ]

    @abstractmethod
    async def scrape(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        The main method to be implemented by each scraper.
        It should navigate to the store's website, scrape the deals, and return them.
        """
        pass

    async def _get_browser(self, playwright):
        """
        Launches a new browser instance with randomized fingerprinting and proxy support.
        """
        browser_args = ["--disable-blink-features=AutomationControlled"]
        if self.proxy:
            browser_args.append(f"--proxy-server={self.proxy}")

        return await playwright.chromium.launch(
            headless=self.headless,
            args=browser_args
        )

    async def _get_context(self, browser):
        """
        Creates a new browser context with a random user agent and other anti-detection measures.
        """
        user_agent = random.choice(self.user_agents)
        return await browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1920, "height": 1080},
            locale="en-CA",
        )

    async def _get_page(self, context):
        """
        Creates a new page and applies stealth measures to it.
        """
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return page

    async def _random_delay(self, min_delay: float = 1.0, max_delay: float = 3.0):
        """
        Waits for a random amount of time to mimic human behavior.
        """
        await asyncio.sleep(random.uniform(min_delay, max_delay))
