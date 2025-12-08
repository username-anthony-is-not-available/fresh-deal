
import asyncio
import random
from playwright.async_api import async_playwright
import os
from bs4 import BeautifulSoup
from typing import List, Dict, Any

class MetroScraper:
    """
    Scraper for Metro.ca.
    Includes fallback to local sample data if live scraping is blocked (common in data centers).
    
    Rate limiting and anti-detection measures:
    - Random delays between requests (2-5 seconds)
    - Realistic user agent rotation
    - Respects robots.txt conceptually (grocery sites typically block scrapers)
    - Automatic fallback to sample data to avoid hammering blocked endpoints
    """
    BASE_URL = "https://www.metro.ca/en"
    CATEGORIES = {
        "Fruits & Vegetables": "https://www.metro.ca/en/online-grocery/aisle/fruits-vegetables",
        "Meat & Poultry": "https://www.metro.ca/en/online-grocery/aisle/meat-poultry"
    }
    
    # Rate limiting settings
    MIN_DELAY_SECONDS = 2.0
    MAX_DELAY_SECONDS = 5.0
    REQUEST_TIMEOUT_MS = 15000
    
    # User agent rotation pool
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    ]

    def __init__(self, headless=True):
        self.headless = headless
        self.items = []
        self.request_count = 0

    async def _random_delay(self):
        """Add a random delay between requests to avoid rate limiting."""
        delay = random.uniform(self.MIN_DELAY_SECONDS, self.MAX_DELAY_SECONDS)
        print(f"Rate limiting: waiting {delay:.1f}s before next request...")
        await asyncio.sleep(delay)

    def _get_random_user_agent(self) -> str:
        """Rotate user agents to appear more human-like."""
        return random.choice(self.USER_AGENTS)

    async def scrape(self, limit: int = 50):
        print("Starting Metro Scraper...")
        print(f"Rate limiting enabled: {self.MIN_DELAY_SECONDS}-{self.MAX_DELAY_SECONDS}s between requests")

        # Try live scraping first
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                
                user_agent = self._get_random_user_agent()
                print(f"Using user agent: {user_agent[:50]}...")
                
                context = await browser.new_context(
                    user_agent=user_agent,
                    viewport={"width": 1920, "height": 1080},
                    locale="en-CA",
                )
                page = await context.new_page()
                
                # Add stealth: hide webdriver property
                await page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """)

                items_scraped = 0
                
                for category_name, url in self.CATEGORIES.items():
                    if items_scraped >= limit:
                        print(f"Reached limit of {limit} items, stopping.")
                        break
                    
                    # Rate limit between category requests
                    if self.request_count > 0:
                        await self._random_delay()
                    
                    self.request_count += 1
                    print(f"Fetching category: {category_name} (request #{self.request_count})")
                    
                    try:
                        await page.goto(url, timeout=self.REQUEST_TIMEOUT_MS, wait_until="domcontentloaded")
                        
                        # Additional random micro-delay to simulate reading
                        await asyncio.sleep(random.uniform(0.5, 1.5))
                        
                        # Check if we got content
                        if await page.locator(".product-tile").count() > 0:
                            print(f"Live scraping successful for {category_name}!")
                            content = await page.content()
                            self.parse_html(content, category_name)
                            items_scraped = len(self.items)
                        else:
                            raise Exception("No products found (likely blocked)")
                            
                    except Exception as e:
                        print(f"Live scraping failed for {category_name}: {e}")
                        print("Falling back to local sample data for POC demonstration.")
                        self.load_sample_data()
                        break  # Don't retry other categories if blocked

                await browser.close()
                
        except Exception as e:
            print(f"Playwright error: {e}")
            self.load_sample_data()

        print(f"Scraping complete. Total requests: {self.request_count}, Items: {len(self.items)}")
        return self.items[:limit]  # Respect the limit

    def load_sample_data(self):
        """Loads sample HTML to simulate successful scraping."""
        try:
            # Path relative to where this script is likely run or absolute
            # Adjust path based on execution context
            base_path = os.path.dirname(__file__)
            path = os.path.join(base_path, "metro_sample.html")

            if os.path.exists(path):
                with open(path, "r") as f:
                    html = f.read()
                self.parse_html(html, "Mixed Category")
            else:
                print(f"Sample file not found at {path}")
        except Exception as e:
            print(f"Error loading sample data: {e}")

    def parse_html(self, html_content: str, category: str):
        soup = BeautifulSoup(html_content, "html.parser")
        tiles = soup.select(".product-tile")

        print(f"Parsing {len(tiles)} tiles from content...")

        for tile in tiles:
            try:
                brand = tile.select_one(".head__brand")
                name = tile.select_one(".head__title")
                price = tile.select_one(".pricing__sale-price")
                weight = tile.select_one(".pi--weight")

                brand_text = brand.get_text(strip=True) if brand else ""
                name_text = name.get_text(strip=True) if name else "Unknown"
                price_text = price.get_text(strip=True) if price else "0.00"
                weight_text = weight.get_text(strip=True) if weight else ""

                # Parse Price
                price_val = 0.0
                clean_price = price_text.replace('$', '').replace(',', '.')

                if '/' in clean_price:
                    # e.g. 2 / $6.00
                    try:
                        parts = clean_price.split('/')
                        qty = float(parts[0].strip())
                        total = float(parts[1].replace('$','').strip())
                        price_val = total / qty
                    except:
                        price_val = 0.0
                else:
                    try:
                        price_val = float(clean_price)
                    except:
                        pass

                # Parse Unit
                unit = "each"
                if 'kg' in weight_text.lower(): unit = 'kg'
                elif 'lb' in weight_text.lower(): unit = 'lb'
                elif ' l' in weight_text.lower(): unit = 'L'
                elif 'ml' in weight_text.lower(): unit = 'ml'
                elif 'g' in weight_text.lower(): unit = 'g'

                item = {
                    "name": f"{brand_text} {name_text}".strip(),
                    "category": category,
                    "price": round(price_val, 2),
                    "original_price": round(price_val, 2), # Default
                    "unit": unit,
                    "store": "Metro"
                }
                self.items.append(item)

            except Exception as e:
                print(f"Error parsing tile: {e}")

if __name__ == "__main__":
    scraper = MetroScraper()
    items = asyncio.run(scraper.scrape())
    print(items)
