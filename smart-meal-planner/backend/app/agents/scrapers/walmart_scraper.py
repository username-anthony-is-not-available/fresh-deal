
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class WalmartScraper:
    """
    Scraper for Walmart.ca that uses the Flipp API.
    This is more reliable than browser-based scraping.
    """
    STORE_NAME = "Walmart"
    BASE_URL = "https://backflipp.wishabi.com/flipp"
    ACCESS_TOKEN = "92bcff5f7d07c3aaa4b33e2c048d7728"
    MERCHANT_ID = 234  # Walmart Canada's ID in Flipp

    DEFAULT_SEARCH_TERMS = [
        "chicken", "beef", "pork", "fish", "salmon",
        "apple", "banana", "orange", "lettuce", "tomato",
        "milk", "cheese", "yogurt", "eggs", "butter",
        "bread", "rice", "pasta", "cereal",
        "juice", "water", "coffee",
        "chips", "cookies", "chocolate",
        "frozen", "pizza", "ice cream"
    ]

    def __init__(self, headless: bool = True, postal_code: str = "H4T1V6", proxy_manager: Optional[Any] = None, storage_path: str = "/tmp"):
        self.postal_code = postal_code

    async def scrape(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrapes Walmart deals by searching for a list of common grocery items
        via the Flipp API.
        """
        deals = []
        seen_items = set()

        async with aiohttp.ClientSession() as session:
            for term in self.DEFAULT_SEARCH_TERMS:
                if len(deals) >= limit:
                    break
                try:
                    url = f"{self.BASE_URL}/items/search"
                    params = {
                        "q": term,
                        "postal_code": self.postal_code,
                        "locale": "en-ca",
                        "access_token": self.ACCESS_TOKEN,
                    }
                    headers = {"User-Agent": "Flipp/5.3.0 (iPhone; iOS 14.7.1; Scale/2.00)"}

                    async with session.get(url, params=params, headers=headers) as response:
                        if response.status != 200:
                            logger.error(f"Flipp API returned status {response.status} for term '{term}'")
                            continue

                        data = await response.json()
                        flyer_items = data.get("items", [])

                        for item in flyer_items:
                            if item.get("merchant_id") != self.MERCHANT_ID:
                                continue

                            if len(deals) >= limit:
                                break

                            parsed_deal = self._parse_flyer_item(item)
                            if parsed_deal:
                                item_key = f"{parsed_deal['name']}|{parsed_deal['price']}"
                                if item_key not in seen_items:
                                    deals.append(parsed_deal)
                                    seen_items.add(item_key)

                except Exception as e:
                    logger.error(f"Error scraping Walmart deals for term '{term}': {e}")

        logger.info(f"Scraped {len(deals)} deals from Walmart via Flipp API.")
        return deals

    def _parse_flyer_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parses a flyer item from the Flipp API response."""
        try:
            name = item.get("name")
            price_text = item.get("current_price")

            if not name or price_text is None:
                return None

            price = float(price_text)
            original_price = float(item.get("original_price", price))

            unit = "each"
            if item.get("post_price_text"):
                if "/lb" in item["post_price_text"].lower():
                    unit = "lb"
                elif "/kg" in item["post_price_text"].lower():
                    unit = "kg"

            return {
                "name": name.strip(),
                "price": price,
                "original_price": original_price,
                "unit": unit,
                "store": self.STORE_NAME,
                "image_url": item.get("clean_image_url"),
                "category": "Flyer"
            }
        except (ValueError, TypeError):
            return None
