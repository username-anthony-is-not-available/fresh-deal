from abc import ABC, abstractmethod
import asyncio
import random
import os
import re
from playwright.async_api import async_playwright, Playwright, Page
from datetime import date, datetime
from bs4 import BeautifulSoup
import logging

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

    async def _handle_cookie_consent(
        self, page: Page, selector: str, timeout: int = 5000
    ) -> bool:
        """
        Handles the cookie consent modal if it appears.
        """
        try:
            if await page.is_visible(selector, timeout=timeout):
                await page.locator(selector).click()
                await page.wait_for_load_state("networkidle", timeout=timeout)
                return True
        except Exception:
            pass
        return False

    async def _scroll_to_bottom(self, page: Page, max_scrolls: int = 5):
        """
        Scrolls to the bottom of the page to trigger lazy loading.
        """
        last_height = await page.evaluate("document.body.scrollHeight")
        for _ in range(max_scrolls):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await self._random_delay(2, 4)
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    async def _save_debug_artifacts(self, page: Page, name: str):
        """
        Saves a screenshot and HTML content for debugging.
        """
        try:
            timestamp = date.today().isoformat()
            screenshot_path = os.path.join(
                self.storage_path, f"{name}_{timestamp}.png"
            )
            html_path = os.path.join(self.storage_path, f"{name}_{timestamp}.html")

            await page.screenshot(path=screenshot_path)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(await page.content())
            print(f"Debug artifacts saved: {screenshot_path}, {html_path}")
        except Exception as e:
            print(f"Failed to save debug artifacts: {e}")

    async def _check_incapsula_block(self, page: Page) -> bool:
        """
        Checks if the page is blocked by Incapsula/Imperva.
        """
        try:
            content = await page.content()
            if "Incapsula incident ID" in content or "Request unsuccessful. Incapsula incident ID" in content:
                print(f"Anti-bot detection triggered (Incapsula) on {page.url}")
                return True
        except Exception:
            pass
        return False

    async def _scrape_flipp_frame(
        self, page: Page, tile_selector: str = 'div[data-testid="product-tile"]'
    ) -> List[BeautifulSoup]:
        """
        Standardized method to locate and extract content from a Flipp-based flyer iframe.
        """
        flyer_frame_selector = 'iframe[title="Main Panel"]'
        flyer_frame = page.frame_locator(flyer_frame_selector)

        try:
            # Wait for the iframe to be present
            await page.wait_for_selector(flyer_frame_selector, timeout=15000)
            # Wait for the tiles to appear in the frame
            tile_locator = flyer_frame.locator(tile_selector)
            await tile_locator.first.wait_for(timeout=15000)

            # Get the HTML from the frame
            frame_content = await flyer_frame.locator('html').inner_html()
            soup = BeautifulSoup(frame_content, 'html.parser')
            return soup.select(tile_selector)
        except Exception as e:
            print(f"Flipp flyer frame not found or timed out on {page.url}: {e}")
            return []

    def _parse_flyer_dates(
        self, date_text: str
    ) -> tuple[Optional[date], Optional[date]]:
        """
        Parses flyer validity dates from text using common patterns.
        Supports both English and French month names common in Quebec flyers.
        """
        if not date_text:
            return None, None

        # Clean text
        date_text = date_text.strip().lower()

        # Translate French months to English for strptime
        french_to_english = {
            "janv.": "jan", "févr.": "feb", "mars": "mar", "avr.": "apr", "mai": "may", "juin": "jun",
            "juil.": "jul", "août": "aug", "sept.": "sep", "oct.": "oct", "nov.": "nov", "déc.": "dec",
            "janvier": "january", "février": "february", "avril": "april", "juillet": "july",
            "août": "august", "septembre": "september", "octobre": "october", "novembre": "november", "décembre": "december"
        }
        for fr, en in french_to_english.items():
            date_text = date_text.replace(fr, en)

        try:
            # Pattern 1: Month Day format (e.g., "from Jan 30 to Feb 5, 2024")
            match = re.search(
                r"(?:from|du)\s+(?P<sm>\w+)\.?\s+(?P<sd>\d+)\s+(?:to|au)\s+(?P<em>\w+)\.?\s+(?P<ed>\d+),?\s+(?P<y>\d{4})",
                date_text,
                re.IGNORECASE,
            )
            if match:
                for fmt in ["%d %b %Y", "%d %B %Y"]:
                    try:
                        start = datetime.strptime(f"{match.group('sd')} {match.group('sm')} {match.group('y')}", fmt).date()
                        end = datetime.strptime(f"{match.group('ed')} {match.group('em')} {match.group('y')}", fmt).date()
                        return start, end
                    except ValueError:
                        continue

            # Pattern 2: Day Month format (e.g., "du 30 janv. au 5 févr. 2024")
            match = re.search(
                r"(?:du|from)\s+(?P<sd>\d+)\s+(?P<sm>\w+)\.?\s+(?:au|to)\s+(?P<ed>\d+)\s+(?P<em>\w+)\.?\s+(?P<y>\d{4})",
                date_text,
                re.IGNORECASE,
            )
            if match:
                for fmt in ["%d %b %Y", "%d %B %Y"]:
                    try:
                        start = datetime.strptime(f"{match.group('sd')} {match.group('sm')} {match.group('y')}", fmt).date()
                        end = datetime.strptime(f"{match.group('ed')} {match.group('em')} {match.group('y')}", fmt).date()
                        return start, end
                    except ValueError:
                        continue

            # Pattern 3: Single month, Month Day to Day (e.g., "from July 25 to 31, 2024")
            match = re.search(
                r"(?:from|du)\s+(?P<m>\w+)\.?\s+(?P<sd>\d+)\s+(?:to|au)\s+(?P<ed>\d+),?\s+(?P<y>\d{4})",
                date_text,
                re.IGNORECASE,
            )
            if match:
                for fmt in ["%d %b %Y", "%d %B %Y"]:
                    try:
                        start = datetime.strptime(f"{match.group('sd')} {match.group('m')} {match.group('y')}", fmt).date()
                        end = datetime.strptime(f"{match.group('ed')} {match.group('m')} {match.group('y')}", fmt).date()
                        return start, end
                    except ValueError:
                        continue

            # Pattern 4: Single month, Day to Day Month (e.g., "du 25 au 31 juillet 2024")
            match = re.search(
                r"(?:du|from)\s+(?P<sd>\d+)\s+(?:au|to)\s+(?P<ed>\d+)\s+(?P<m>\w+)\.?\s+(?P<y>\d{4})",
                date_text,
                re.IGNORECASE,
            )
            if match:
                for fmt in ["%d %b %Y", "%d %B %Y"]:
                    try:
                        start = datetime.strptime(f"{match.group('sd')} {match.group('m')} {match.group('y')}", fmt).date()
                        end = datetime.strptime(f"{match.group('ed')} {match.group('m')} {match.group('y')}", fmt).date()
                        return start, end
                    except ValueError:
                        continue
        except Exception:
            pass

        return None, None

    def _parse_price(self, price_text: str) -> Optional[float]:
        """Parse price from various formats (e.g., '2,99$', '$2.99', '2 pour 5$')."""
        if not price_text:
            return None

        # Clean up the text
        price_text = price_text.strip().lower()
        # Replace non-breaking spaces and other weird whitespace
        price_text = re.sub(r'\s+', ' ', price_text)

        # Handle "X pour Y$" or "X for Y$" or "X/$Y" or "$Y/X"
        # 1. X pour/for/$ Y (e.g., "2 pour 5,00$")
        # Ensure we don't match if there's a $ right before the quantity
        multi_match = re.search(
            r"(?<![\$\d])(\d+)\s*(?:pour|for|/|ea\.)\s*[\$]?\s*(\d+[,.]?\d*)\s*\$?", price_text
        )
        if multi_match:
            try:
                quantity = int(multi_match.group(1))
                total = float(multi_match.group(2).replace(",", "."))
                return round(total / quantity, 2)
            except (ValueError, ZeroDivisionError):
                pass

        # 2. $Y / X or $Y ea.
        multi_match_reverse = re.search(
            r"[\$]?\s*(\d+[,.]?\d*)\s*\$?\s*(?:/|ea\.|pour|for)\s*(\d+)", price_text
        )
        if multi_match_reverse:
            try:
                total = float(multi_match_reverse.group(1).replace(",", "."))
                quantity = int(multi_match_reverse.group(2))
                return round(total / quantity, 2)
            except (ValueError, ZeroDivisionError):
                pass

        # 3. Handle cent prices (e.g. 88¢ or 88c)
        cent_match = re.search(r"(\d+)\s*(?:¢|c\b)", price_text)
        if cent_match:
            try:
                return round(float(cent_match.group(1)) / 100, 2)
            except ValueError:
                pass

        # Handle standard price formats
        price_match = re.search(r"(\d+[,.]?\d*)\s*\$?", price_text)
        if price_match:
            try:
                return float(price_match.group(1).replace(",", "."))
            except ValueError:
                pass

        return None

    def _extract_unit(self, text: str) -> str:
        """Extract unit from product description."""
        text_lower = text.lower()

        # Prioritize weight-based units
        # Use regex that allows digits before the unit (e.g., 1kg, 500g)
        if re.search(r"(?:\d+|\b)kg\b|/kg\b|\bpar kg\b|\bkilo", text_lower):
            return "kg"
        elif re.search(r"(?:\d+|\b)lb\b|/lb\b|\bpar lb\b|\bpound", text_lower):
            return "lb"
        elif re.search(r"100\s*g\b|/100\s*g\b", text_lower):
            return "100g"
        elif re.search(r"\bml\b", text_lower):
            return "ml"
        elif re.search(r"(?:\d+)\s*g\b|\bgramme", text_lower):
            return "g"
        elif re.search(r"(?:\d+)\s*l\b|\blitre", text_lower):
            return "L"
        else:
            return "each"

    def _parse_discount(self, text: str) -> Optional[float]:
        """Parse discount percentage from text."""
        if not text:
            return None

        # Look for percentage patterns
        pct_match = re.search(r"(\d+)\s*%", text)
        if pct_match:
            return float(pct_match.group(1))

        return None

    def _calculate_original_price(
        self, price: Optional[float], discount_pct: Optional[float]
    ) -> float:
        """Calculate original price from discounted price and percentage."""
        if price is None:
            return 0.0
        if discount_pct is None or discount_pct <= 0:
            return price

        return round(price / (1 - discount_pct / 100), 2)

    def _categorize_product(self, name: str) -> str:
        """Categorize product based on name."""
        name_lower = name.lower()

        categories = {
            "Beverages": [
                "jus",
                "juice",
                "eau",
                "water",
                "café",
                "coffee",
                "thé",
                "tea",
                "boisson",
                "drink",
                "soda",
                "liqueur",
            ],
            "Snacks": [
                "chips",
                "biscuit",
                "cookie",
                "chocolat",
                "chocolate",
                "bonbon",
                "candy",
                "noix",
                "nuts",
            ],
            "Meat & Poultry": [
                "poulet",
                "chicken",
                "boeuf",
                "beef",
                "porc",
                "pork",
                "viande",
                "meat",
                "saucisse",
                "sausage",
                "bacon",
                "jambon",
                "ham",
                "turkey",
                "dinde",
            ],
            "Seafood": [
                "poisson",
                "fish",
                "saumon",
                "salmon",
                "crevette",
                "shrimp",
                "thon",
                "tuna",
                "fruits de mer",
                "seafood",
                "cod",
                "morue",
            ],
            "Fruits": [
                "pomme",
                "apple",
                "banane",
                "banana",
                "orange",
                "fraise",
                "strawberry",
                "raisin",
                "grape",
                "fruit",
                "melon",
                "berry",
                "bleuet",
            ],
            "Vegetables": [
                "légume",
                "vegetable",
                "carotte",
                "carrot",
                "tomate",
                "tomato",
                "laitue",
                "lettuce",
                "brocoli",
                "broccoli",
                "oignon",
                "onion",
                "pomme de terre",
                "potato",
                "poivron",
                "pepper",
            ],
            "Dairy & Eggs": [
                "lait",
                "milk",
                "fromage",
                "cheese",
                "yogourt",
                "yogurt",
                "oeuf",
                "egg",
                "beurre",
                "butter",
                "crème",
                "cream",
            ],
            "Bakery": [
                "pain",
                "bread",
                "baguette",
                "croissant",
                "muffin",
                "gâteau",
                "cake",
                "bagel",
            ],
            "Pantry": [
                "riz",
                "rice",
                "pâtes",
                "pasta",
                "céréale",
                "cereal",
                "sauce",
                "soupe",
                "soup",
                "conserve",
                "canned",
                "huile",
                "oil",
                "farine",
                "flour",
                "sucre",
                "sugar",
                "épice",
                "spice",
                "sel",
                "salt",
                "poivre",
                "pepper",
            ],
            "Frozen": [
                "surgelé",
                "frozen",
                "glace",
                "ice cream",
                "pizza",
                "poche",
                "pocket",
            ],
            "Household": [
                "papier",
                "paper",
                "savon",
                "soap",
                "détergent",
                "detergent",
                "nettoyeur",
                "cleaner",
                "mouchoir",
                "tissue",
                "sac",
                "bag",
            ],
            "Personal Care": [
                "shampoing",
                "shampoo",
                "dentifrice",
                "toothpaste",
                "brosse à dents",
                "toothbrush",
                "déodorant",
                "deodorant",
                "soin",
                "care",
            ],
        }

        for category, keywords in categories.items():
            if any(kw in name_lower for kw in keywords):
                return category

        return "Grocery"
