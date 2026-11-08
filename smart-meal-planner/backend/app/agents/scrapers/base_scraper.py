from abc import ABC, abstractmethod
import asyncio
import random
import os
import re
import logging
from playwright.async_api import async_playwright, Playwright, Page
from datetime import date, datetime
from bs4 import BeautifulSoup

try:
    # playwright-stealth exposes helper functions, not a Stealth class.
    from playwright_stealth import stealth_async
except Exception:  # pragma: no cover
    stealth_async = None
from typing import List, Dict, Any, Optional, Tuple
from app.core.proxy_manager import ProxyManager
from app.core.config import settings
from datetime import timedelta
import json
from .user_agents import USER_AGENTS

# Loyalty programs mapping
LOYALTY_PROGRAMS = {
    "PC Optimum": ["PC Optimum", "Optimum"],
    "Scene+": ["Scene+"],
    "Moi": ["Moi"],
    "AIR MILES": ["AIR MILES", "Air Miles"]
}



LOYALTY_POINT_VALUES = {
    "PC Optimum": 0.001,  # 1000 pts = $1.00 (Maxi, Provigo)
    "Scene+": 0.01,       # 1000 pts = $10.00 (IGA)
    "Moi": 0.008,         # 500 pts = $4.00 (Metro, Super C)
    "AIR MILES": 0.105,   # ~10.5 cents per mile
}

def calculate_effective_loyalty_price(
    price: float,
    loyalty_points: Optional[int] = None,
    loyalty_program: Optional[str] = None,
    member_price: Optional[float] = None
) -> Tuple[float, float]:
    """
    Returns (effective_price, loyalty_savings).
    Converts Quebec grocery loyalty points bonuses and member pricing into CAD discounts.
    """
    effective = member_price if member_price and member_price < price else price
    savings = 0.0
    if member_price and member_price < price:
        savings += (price - member_price)

    if loyalty_points and loyalty_points > 0 and loyalty_program:
        for prog, val in LOYALTY_POINT_VALUES.items():
            if prog.lower() in loyalty_program.lower():
                point_discount = loyalty_points * val
                savings += point_discount
                effective = max(0.01, effective - point_discount)
                break
    return round(effective, 2), round(savings, 2)


class BaseScraper(ABC):
    """
    Abstract base class for all store-specific scrapers.
    Provides a common interface and shared functionalities for browser automation.
    """

    def __init__(
        self,
        postal_code: Optional[str] = None,
        headless: bool = True,
        proxy_manager: Optional[ProxyManager] = None,
        storage_path: str = "/tmp/scrapers",
    ):
        self.postal_code = postal_code or getattr(settings, "LOCAL_POSTAL_CODE", None) or settings.DEFAULT_POSTAL_CODE
        self.headless = headless
        self.proxy_manager = proxy_manager or ProxyManager()
        self.storage_path = storage_path
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path, exist_ok=True)

        self.storage_state_path = os.path.join(
            storage_path, f"browser_storage_state_{self.__class__.__name__}.json"
        )
        self.user_agents = USER_AGENTS
        self.last_screenshot: Optional[str] = None
        self.last_html: Optional[str] = None

    @staticmethod
    def get_flyer_week_id(dt: Optional[datetime] = None) -> str:
        if dt is None:
            dt = datetime.now()
        days_since_thursday = (dt.weekday() - 3) % 7
        thursday = dt - timedelta(days=days_since_thursday)
        return thursday.strftime("%Y_%m_%d")

    def _get_cache_path(self) -> str:
        cache_dir = os.path.join(os.getcwd(), ".cache", "flyers")
        os.makedirs(cache_dir, exist_ok=True)
        week_id = self.get_flyer_week_id()
        store_key = self.__class__.__name__.lower().replace("scraper", "")
        return os.path.join(cache_dir, f"{store_key}_{week_id}.json")

    def load_cached_payload(self) -> Optional[List[Dict[str, Any]]]:
        cache_file = self._get_cache_path()
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        logging.info(f"Loaded {len(data)} cached deals from {cache_file}")
                        return data
            except Exception as e:
                logging.warning(f"Failed to read flyer cache {cache_file}: {e}")
        return None

    def save_cached_payload(self, deals: List[Dict[str, Any]]):
        if not deals:
            return
        cache_file = self._get_cache_path()
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(deals, f, ensure_ascii=False, indent=2, default=str)
                logging.info(f"Cached {len(deals)} deals to {cache_file}")
        except Exception as e:
            logging.warning(f"Failed to write flyer cache {cache_file}: {e}")

    def parse_html(self, html_content: str) -> List[Any]:
        """
        Static/HTML-based parsing logic for offline snapshots or regression testing.
        Subclasses should override if they support direct HTML string parsing.
        """
        return []

    @abstractmethod
    async def _scrape_page(self, page: Page, limit: int) -> List[Dict[str, Any]]:
        """
        The main scraping logic to be implemented by each scraper subclass.
        This method receives a configured Page object.
        """
        pass

    async def scrape(self, limit: int = 50) -> tuple[List[Dict[str, Any]], Optional[str], Optional[str], Optional[str]]:
        """
        The main method that handles browser setup, teardown, and proxy rotation.
        It calls the _scrape_page method where the actual scraping logic resides.
        Returns a tuple of (deals, proxy_used, screenshot_path, html_path).
        """
        # Check local disk cache first (Thursday-Wednesday weekly circular)
        cached = self.load_cached_payload()
        if cached:
            return cached[:limit], "disk_cache", None, None

        proxy = self.proxy_manager.get_proxy()
        screenshot_path = None
        html_path = None

        async with async_playwright() as p:
            browser = None
            try:
                browser = await self._get_browser(p, proxy)
                context = await self._get_context(browser)
                page = await self._get_page(context)

                # Check for Incapsula block immediately after loading
                # (Assuming the implementation will navigate to the URL)
                # Subclasses should call this check.

                await self._simulate_mouse_movement(page)
                deals = await self._scrape_page(page, limit)

                # Check if it was blocked at any point
                if await self._check_incapsula_block(page):
                    self.last_screenshot, self.last_html = await self._save_debug_artifacts(page, f"{self.__class__.__name__}_blocked")
                    raise Exception("[BOT_BLOCK] Anti-bot detection triggered (Incapsula)")

                await context.storage_state(path=self.storage_state_path)
                if deals:
                    self.save_cached_payload(deals)
                return deals, proxy, None, None
            except Exception as e:
                error_msg = str(e)
                logging.error(f"Scraping failed with proxy {proxy}: {error_msg}")

                # Save debug artifacts on failure if not already saved (e.g. by _check_incapsula_block)
                if not self.last_screenshot:
                    try:
                        # We might not have 'page' if it failed before page creation,
                        # but usually it fails during _scrape_page
                        if 'page' in locals():
                            self.last_screenshot, self.last_html = await self._save_debug_artifacts(page, f"{self.__class__.__name__}_failure")
                    except Exception as artifact_error:
                        logging.error(f"Failed to save artifacts during exception handling: {artifact_error}")

                if "Incapsula" in error_msg or "Anti-bot" in error_msg:
                    # Specific handling for bot detection - blacklist proxy longer if possible
                    if proxy:
                        self.proxy_manager.blacklist_proxy(proxy)
                    if "[BOT_BLOCK]" not in error_msg:
                        error_msg = f"[BOT_BLOCK] {error_msg}"
                    raise Exception(error_msg)

                if "Timeout" in error_msg or "timeout" in error_msg:
                    if "[TIMEOUT]" not in error_msg:
                        error_msg = f"[TIMEOUT] {error_msg}"
                    raise Exception(error_msg)

                if proxy:
                    # General failure, still blacklist proxy but might be structure change
                    self.proxy_manager.blacklist_proxy(proxy)

                # Re-raise with the same type.
                # Artifact paths are now stored in self.last_screenshot and self.last_html
                raise e
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

    async def _random_delay(self, min_delay: float = 1.5, max_delay: float = 3.0):
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

    async def _save_debug_artifacts(self, page: Page, name: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Saves a screenshot and HTML content for debugging.
        Returns a tuple of (screenshot_path, html_path).
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_filename = f"{name}_{timestamp}.png"
            html_filename = f"{name}_{timestamp}.html"
            screenshot_path = os.path.join(self.storage_path, screenshot_filename)
            html_path = os.path.join(self.storage_path, html_filename)

            await page.screenshot(path=screenshot_path)
            content = await page.content()
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(content)
            logging.info(f"Debug artifacts saved: {screenshot_path}, {html_path}")
            return screenshot_path, html_path
        except Exception as e:
            logging.error(f"Failed to save debug artifacts: {e}")
            return None, None

    async def _check_incapsula_block(self, page: Page) -> bool:
        """
        Checks if the page is blocked by Incapsula/Imperva.
        """
        try:
            content = await page.content()
            if "Incapsula incident ID" in content or "Request unsuccessful. Incapsula incident ID" in content:
                logging.warning(f"Anti-bot detection triggered (Incapsula) on {page.url}")
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
            logging.error(f"Flipp flyer frame not found or timed out on {page.url}: {e}")
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
            "juil.": "jul", "août": "august", "sept.": "sep", "oct.": "oct", "nov.": "nov", "déc.": "dec",
            "janvier": "january", "février": "february", "avril": "april", "juillet": "july",
            "septembre": "september", "octobre": "october", "novembre": "november", "décembre": "december"
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

        # Ignore marketing patterns that contain numbers but aren't prices
        # e.g., "Buy 1 get 1 free", "2nd at 50% off"
        marketing_ignore = [
            r"buy \d+ get \d+",
            r"\d+(?:st|nd|rd|th) at \d+%",
            r"save \$\d+[,.]?\d*",
            r"rabais de \d+[,.]?\d*\s*\$",
            r"limit \d+",
            r"limite \d+"
        ]
        for pattern in marketing_ignore:
            price_text = re.sub(pattern, "", price_text)

        # Handle "X pour Y$" or "X for Y$" or "X/$Y" or "$Y/X" or "X ch." or "X l'unité"
        # 1. X pour/for/$ Y (e.g., "2 pour 5,00$")
        # Ensure we don't match if there's a $ right before the quantity
        multi_match = re.search(
            r"(?<![\$\d])(\d+)\s*(?:pour|for|/|ea\.|ch\.|l'unité)\s*[\$]?\s*(\d+[,.]?\d*)\s*\$?", price_text
        )
        if multi_match:
            try:
                quantity = int(multi_match.group(1))
                total = float(multi_match.group(2).replace(",", "."))
                return round(total / quantity, 2)
            except (ValueError, ZeroDivisionError):
                pass

        # 2. $Y / X or $Y ea. or $Y ch. or $Y l'unité
        multi_match_reverse = re.search(
            r"[\$]?\s*(\d+[,.]?\d*)\s*\$?\s*(?:/|ea\.|ch\.|l'unité|pour|for)\s*(\d+)", price_text
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
        # We want to be careful not to match random numbers if a $ is present elsewhere
        price_match = re.search(r"(\d+[,.]?\d*)\s*\$|\$\s*(\d+[,.]?\d*)", price_text)
        if price_match:
            try:
                val = price_match.group(1) or price_match.group(2)
                return float(val.replace(",", "."))
            except ValueError:
                pass

        # Fallback for just a number if no $ was found in the whole string
        if "$" not in price_text:
            price_match = re.search(r"(\d+[,.]\d{2})", price_text)
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
        elif re.search(r"\bsac\b|\bbte\b|\bboîte\b|\bbox\b", text_lower):
            return "sac/box"
        elif re.search(r"\bpqt\b|\bpaquet\b|\bpack\b", text_lower):
            return "pack"
        elif re.search(r"\bcaisse\b|\bcase\b", text_lower):
            return "case"
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

    def _parse_loyalty_points(self, text: str) -> Optional[Tuple[str, int]]:
        """Parse loyalty points from text, e.g., 'Earn 2000 PC Optimum points'."""
        if not text:
            return None

        text_lower = text.lower()
        for program, keywords in LOYALTY_PROGRAMS.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    # Regex to find numbers, handling commas
                    match = re.search(r'(\d{1,3}(,\d{3})*|\d+)\s*(points)?', text_lower)
                    if match:
                        try:
                            points_str = match.group(1).replace(',', '')
                            return program, int(points_str)
                        except (ValueError, IndexError):
                            continue
        return None

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
                "sucre à la crème",
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
                "tourtière",
                "ragoût",
                "cipaille",
                "pâté chinois",
                "agneau",
                "lamb",
                "veau",
                "veal",
                "canard",
                "duck",
            ],
            "Deli": [
                "creton",
                "smoked meat",
                "boudin",
                "salami",
                "pastrami",
                "pâté",
                "charcuterie",
                "pepperoni",
                "bologne",
                "bologna",
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
                "sirop d'érable",
                "maple syrup",
                "miel",
                "honey",
                "beurre d'arachide",
                "peanut butter",
                "confiture",
                "jam",
                "moutarde",
                "mustard",
                "ketchup",
                "mayonnaise",
            ],
            "International": [
                "hummus",
                "tofu",
                "miso",
                "soy sauce",
                "soja",
                "tacos",
                "salsa",
                "curry",
                "couscous",
                "quinoa",
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
