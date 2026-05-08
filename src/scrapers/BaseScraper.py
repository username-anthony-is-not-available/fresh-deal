from abc import ABC, abstractmethod
import asyncio
import random
import os
import re
import logging
from datetime import datetime, date
from typing import List, Optional, Tuple
from playwright.async_api import async_playwright, Playwright, Page, BrowserContext
from bs4 import BeautifulSoup

try:
    from playwright_stealth import stealth_async
except ImportError:
    stealth_async = None

from src.core.proxy_manager import ProxyManager
from src.core.schema_validator import Deal

logger = logging.getLogger(__name__)

# Loyalty programs mapping
LOYALTY_PROGRAMS = {
    "PC Optimum": ["PC Optimum", "Optimum"],
    "Scene+": ["Scene+"],
    "Moi": ["Moi"],
    "AIR MILES": ["AIR MILES", "Air Miles"]
}

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

                await self._simulate_mouse_movement(page)

                # Check for Incapsula block
                if await self._check_incapsula_block(page):
                    self.last_screenshot, self.last_html = await self._save_debug_artifacts(page, f"{self.__class__.__name__}_blocked")
                    raise Exception("[BOT_BLOCK] Anti-bot detection triggered (Incapsula)")

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
        """
        for char in text:
            await page.type(selector, char)
            await self._random_delay(min_delay, max_delay)

    async def _handle_cookie_consent(self, page: Page, selector: str, timeout: int = 5000) -> bool:
        """
        Clicks the cookie consent button if present.
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
        Scrolls down to load lazy content.
        """
        last_height = await page.evaluate("document.body.scrollHeight")
        for _ in range(max_scrolls):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await self._random_delay(2, 4)
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

    async def _check_incapsula_block(self, page: Page) -> bool:
        """
        Checks if the page is blocked by Incapsula/Imperva.
        """
        try:
            content = await page.content()
            if "Incapsula incident ID" in content or "Request unsuccessful. Incapsula incident ID" in content:
                logger.warning(f"Anti-bot detection triggered (Incapsula) on {page.url}")
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
            logger.error(f"Flipp flyer frame not found or timed out on {page.url}: {e}")
            return []

    def _parse_flyer_dates(self, date_text: str) -> Tuple[Optional[date], Optional[date]]:
        """
        Parses flyer validity dates from text using common patterns.
        """
        if not date_text:
            return None, None

        date_text = date_text.strip().lower()
        french_to_english = {
            "janv.": "jan", "févr.": "feb", "mars": "mar", "avr.": "apr", "mai": "may", "juin": "jun",
            "juil.": "jul", "août": "august", "sept.": "sep", "oct.": "oct", "nov.": "nov", "déc.": "dec",
            "janvier": "january", "février": "february", "avril": "april", "juillet": "july",
            "septembre": "september", "octobre": "october", "novembre": "november", "décembre": "december"
        }
        for fr, en in french_to_english.items():
            date_text = date_text.replace(fr, en)

        try:
            # Pattern 1: du 1 au 7 janv. 2024 / from 1 to 7 Jan. 2024
            match = re.search(
                r"(?:from|du)\s+(?P<sd>\d+)\s+(?:to|au)\s+(?P<ed>\d+)\s+(?P<m>\w+)\.?\s+(?P<y>\d{4})",
                date_text, re.IGNORECASE
            )
            if match:
                for fmt in ["%d %b %Y", "%d %B %Y"]:
                    try:
                        start = datetime.strptime(f"{match.group('sd')} {match.group('m')} {match.group('y')}", fmt).date()
                        end = datetime.strptime(f"{match.group('ed')} {match.group('m')} {match.group('y')}", fmt).date()
                        return start, end
                    except ValueError:
                        continue

            # Pattern 2: du 1 janv. 2024 au 7 janv. 2024
            match = re.search(
                r"(?:from|du)\s+(?P<sd>\d+)\s+(?P<sm>\w+)\.?\s+(?P<y1>\d{4})?\s*(?:to|au)\s+(?P<ed>\d+)\s+(?P<em>\w+)\.?\s+(?P<y>\d{4})",
                date_text, re.IGNORECASE
            )
            if match:
                year = match.group('y')
                for fmt in ["%d %b %Y", "%d %B %Y"]:
                    try:
                        start = datetime.strptime(f"{match.group('sd')} {match.group('sm')} {year}", fmt).date()
                        end = datetime.strptime(f"{match.group('ed')} {match.group('em')} {year}", fmt).date()
                        return start, end
                    except ValueError:
                        continue

            # Pattern 3: from Jan 1 to Jan 7, 2024
            match = re.search(
                r"(?:from|du)\s+(?P<sm>\w+)\.?\s+(?P<sd>\d+)\s+(?:to|au)\s+(?P<em>\w+)\.?\s+(?P<ed>\d+),?\s+(?P<y>\d{4})",
                date_text, re.IGNORECASE
            )
            if match:
                for fmt in ["%d %b %Y", "%d %B %Y"]:
                    try:
                        start = datetime.strptime(f"{match.group('sd')} {match.group('sm')} {match.group('y')}", fmt).date()
                        end = datetime.strptime(f"{match.group('ed')} {match.group('em')} {match.group('y')}", fmt).date()
                        return start, end
                    except ValueError:
                        continue
        except Exception:
            pass
        return None, None

    def _parse_price(self, price_text: str) -> Optional[float]:
        """Parse price from various formats."""
        if not price_text:
            return None
        price_text = price_text.strip().lower()
        price_text = re.sub(r'\s+', ' ', price_text)

        marketing_ignore = [
            r"buy \d+ get \d+", r"\d+(?:st|nd|rd|th) at \d+%", r"save \$\d+[,.]?\d*",
            r"rabais de \d+[,.]?\d*\s*\$", r"limit \d+", r"limite \d+"
        ]
        for pattern in marketing_ignore:
            price_text = re.sub(pattern, "", price_text)

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

        cent_match = re.search(r"(\d+)\s*(?:¢|c\b)", price_text)
        if cent_match:
            try:
                return round(float(cent_match.group(1)) / 100, 2)
            except ValueError:
                pass

        price_match = re.search(r"(\d+[,.]?\d*)\s*\$|\$\s*(\d+[,.]?\d*)", price_text)
        if price_match:
            try:
                val = price_match.group(1) or price_match.group(2)
                return float(val.replace(",", "."))
            except ValueError:
                pass

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
        if re.search(r"(?:\d+|\b)kg\b|/kg\b|\bpar kg\b|\bkilo", text_lower):
            return "kg"
        elif re.search(r"(?:\d+|\b)lb\b|/lb\b|\bpar lb\b|\bpound", text_lower):
            return "lb"
        elif re.search(r"100\s*g\b|/100\s*g\b", text_lower):
            return "100g"
        elif re.search(r"(?:\d+|\b)ml\b", text_lower):
            return "ml"
        elif re.search(r"(?:\d+|\b)g\b|\bgramme", text_lower):
            return "g"
        elif re.search(r"(?:\d+|\b)l\b|\blitre", text_lower):
            return "L"
        elif re.search(r"\bsac\b|\bbte\b|\bboîte\b|\bbox\b|\bbag\b", text_lower):
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
        pct_match = re.search(r"(\d+)\s*%", text)
        return float(pct_match.group(1)) if pct_match else None

    def _calculate_original_price(self, price: Optional[float], discount_pct: Optional[float]) -> float:
        """Calculate original price from discounted price and percentage."""
        if price is None:
            return 0.0
        if discount_pct is None or discount_pct <= 0:
            return price
        return round(price / (1 - discount_pct / 100), 2)

    def _parse_loyalty_points(self, text: str) -> Optional[Tuple[str, int]]:
        """Parse loyalty points from text."""
        if not text:
            return None
        text_lower = text.lower()
        for program, keywords in LOYALTY_PROGRAMS.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
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
            "Beverages": ["jus", "juice", "eau", "water", "café", "coffee", "thé", "tea", "boisson", "drink", "soda", "liqueur"],
            "Snacks": ["chips", "biscuit", "cookie", "chocolat", "chocolate", "bonbon", "candy", "noix", "nuts", "sucre à la crème"],
            "Meat & Poultry": ["poulet", "chicken", "boeuf", "beef", "porc", "pork", "viande", "meat", "saucisse", "sausage", "bacon", "jambon", "ham", "turkey", "dinde", "tourtière", "ragoût", "cipaille", "pâté chinois", "agneau", "lamb", "veau", "veal", "canard", "duck"],
            "Deli": ["creton", "smoked meat", "boudin", "salami", "pastrami", "pâté", "charcuterie", "pepperoni", "bologne", "bologna"],
            "Seafood": ["poisson", "fish", "saumon", "salmon", "crevette", "shrimp", "thon", "tuna", "fruits de mer", "seafood", "cod", "morue"],
            "Fruits": ["pomme", "apple", "banane", "banana", "orange", "fraise", "strawberry", "raisin", "grape", "fruit", "melon", "berry", "bleuet"],
            "Vegetables": ["légume", "vegetable", "carotte", "carrot", "tomate", "tomato", "laitue", "lettuce", "brocoli", "broccoli", "oignon", "onion", "pomme de terre", "potato", "poivron", "pepper"],
            "Dairy & Eggs": ["lait", "milk", "fromage", "cheese", "yogourt", "yogurt", "oeuf", "egg", "beurre", "butter", "crème", "cream"],
            "Bakery": ["pain", "bread", "baguette", "croissant", "muffin", "gâteau", "cake", "bagel"],
            "Pantry": ["riz", "rice", "pâtes", "pasta", "céréale", "cereal", "sauce", "soupe", "soup", "conserve", "canned", "huile", "oil", "farine", "flour", "sucre", "sugar", "épice", "spice", "sel", "salt", "poivre", "pepper", "sirop d'érable", "maple syrup", "miel", "honey", "beurre d'arachide", "peanut butter", "confiture", "jam", "moutarde", "mustard", "ketchup", "mayonnaise"],
            "International": ["hummus", "tofu", "miso", "soy sauce", "soja", "tacos", "salsa", "curry", "couscous", "quinoa"],
            "Frozen": ["surgelé", "frozen", "glace", "ice cream", "pizza", "poche", "pocket"],
            "Household": ["papier", "paper", "savon", "soap", "détergent", "detergent", "nettoyeur", "cleaner", "mouchoir", "tissue", "sac", "bag"],
            "Personal Care": ["shampoing", "shampoo", "dentifrice", "toothpaste", "brosse à dents", "toothbrush", "déodorant", "deodorant", "soin", "care"],
        }
        for category, keywords in categories.items():
            if any(re.search(r'\b' + re.escape(kw) + r'\b', name_lower) for kw in keywords):
                return category
        return "Grocery"
