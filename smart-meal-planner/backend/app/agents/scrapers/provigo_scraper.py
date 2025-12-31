
import asyncio
import aiohttp
import re
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ProvigoScraper:
    """
    Scraper for Provigo.ca that uses the Flipp API.
    """
    STORE_NAME = "Provigo"
    BASE_URL = "https://backflipp.wishabi.com/flipp"
    MERCHANT_ID = 2338

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
                    }
                    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

                    async with session.get(url, params=params, headers=headers) as response:
                        if response.status != 200:
                            logger.error(f"Flipp API returned status {response.status} for term '{term}'")
                            continue

                        data = await response.json()
                        flyer_items = data.get("items", [])

                        for item in flyer_items:
                            if int(item.get("merchant_id")) != self.MERCHANT_ID:
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
                    logger.error(f"Error scraping Provigo deals for term '{term}': {e}")

        logger.info(f"Scraped {len(deals)} deals from Provigo via Flipp API.")
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
                post_price_text = item.get("post_price_text")
                if post_price_text is not None:
                    if "/lb" in post_price_text.lower():
                        unit = "lb"
                    elif "/kg" in post_price_text.lower():
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
