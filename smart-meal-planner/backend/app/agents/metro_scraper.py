
import asyncio
from playwright.async_api import async_playwright
import os
from bs4 import BeautifulSoup
from typing import List, Dict, Any

class MetroScraper:
    """
    Scraper for Metro.ca.
    Includes fallback to local sample data if live scraping is blocked (common in data centers).
    """
    BASE_URL = "https://www.metro.ca/en"
    CATEGORIES = {
        "Fruits & Vegetables": "https://www.metro.ca/en/online-grocery/aisle/fruits-vegetables",
        "Meat & Poultry": "https://www.metro.ca/en/online-grocery/aisle/meat-poultry"
    }

    def __init__(self, headless=True):
        self.headless = headless
        self.items = []

    async def scrape(self, limit: int = 50):
        print("Starting Metro Scraper...")

        # Try live scraping first
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                context = await browser.new_context(
                     user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                # Attempt to hit a category directly
                url = list(self.CATEGORIES.values())[0]
                try:
                    await page.goto(url, timeout=15000, wait_until="domcontentloaded")
                    # Check if we got content
                    if await page.locator(".product-tile").count() > 0:
                        print("Live scraping successful (unexpectedly!). Parsing...")
                        # Logic to parse live page would go here
                        # For now, if this magically works, we can try to parse.
                        content = await page.content()
                        self.parse_html(content, "Fruits & Vegetables")
                    else:
                        raise Exception("No products found (likely blocked)")
                except Exception as e:
                    print(f"Live scraping failed or blocked: {e}")
                    print("Falling back to local sample data for POC demonstration.")
                    self.load_sample_data()

                await browser.close()
        except Exception as e:
             print(f"Playwright error: {e}")
             self.load_sample_data()

        return self.items

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
