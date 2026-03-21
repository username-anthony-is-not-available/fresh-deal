"""
Flipp API Scraper - Reliable grocery deal aggregator

Flipp (flipp.com) is a digital flyer platform used by most major Canadian
and US grocery stores. They expose a public search API that we can use
to get real grocery deals without browser automation.

Supported Canadian stores include:
- Metro (ID: 2269)
- Maxi (ID: 2349)
- Provigo (ID: 2338)
- Super C (ID: 2585)
- Loblaws (ID: 2018)
- Walmart (ID: 234)
- Food Basics (ID: 2265)
- IGA (ID: 3559)
- No Frills (ID: 2554)
- Real Canadian Superstore (ID: 2271)
"""

import asyncio
import aiohttp
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import random


@dataclass
class GroceryStore:
    """Represents a grocery store in the Flipp network."""
    id: int
    name: str


# Loyalty programs mapping
LOYALTY_PROGRAMS = {
    "PC Optimum": ["PC Optimum", "Optimum"],
    "Scene+": ["Scene+"],
    "Moi": ["Moi"],
    "AIR MILES": ["AIR MILES", "Air Miles"]
}


# Major Canadian grocery stores on Flipp
CANADIAN_STORES = {
    "metro": GroceryStore(2269, "Metro"),
    "maxi": GroceryStore(2349, "Maxi"),
    "provigo": GroceryStore(2338, "Provigo"),
    "super_c": GroceryStore(2585, "Super C"),
    "loblaws": GroceryStore(2018, "Loblaws"),
    "walmart": GroceryStore(234, "Walmart"),
    "food_basics": GroceryStore(2265, "Food Basics"),
    "iga": GroceryStore(3559, "IGA"),
    "no_frills": GroceryStore(2554, "No Frills"),
    "real_canadian_superstore": GroceryStore(2271, "Real Canadian Superstore"),
}


class FlippScraper:
    """
    Scraper that uses the Flipp public API to get grocery deals.
    
    This is much more reliable than browser scraping because:
    1. It's a public API (no Cloudflare/bot protection)
    2. It aggregates data from multiple stores
    3. Data is already structured (no HTML parsing needed)
    4. Much faster than browser automation
    """
    
    BASE_URL = "https://backflipp.wishabi.com/flipp"
    
    # Common grocery search terms for comprehensive scraping
    DEFAULT_SEARCH_TERMS = [
        "chicken", "beef", "pork", "fish", "salmon",
        "apple", "banana", "orange", "lettuce", "tomato",
        "milk", "cheese", "yogurt", "eggs", "butter",
        "bread", "rice", "pasta", "cereal",
        "juice", "water", "coffee",
        "chips", "cookies", "chocolate",
        "frozen", "pizza", "ice cream"
    ]
    
    # Rate limiting
    MIN_DELAY_SECONDS = 0.5  # Flipp API is more permissive
    MAX_DELAY_SECONDS = 1.5
    
    def __init__(
        self, 
        postal_code: str = "H4T1V6",  # Default: Montreal area
        locale: str = "en-ca",
        stores: Optional[List[str]] = None
    ):
        """
        Initialize the Flipp scraper.
        
        Args:
            postal_code: Canadian postal code for location-based deals
            locale: Locale for API responses (en-ca, fr-ca)
            stores: List of store keys to filter by (e.g., ["metro", "maxi"])
                   If None, includes all stores
        """
        self.postal_code = postal_code
        self.locale = locale
        self.stores = stores
        self.items: List[Dict[str, Any]] = []
        self.seen_items: set = set()  # Deduplicate by name+store
        
    async def _random_delay(self):
        """Add a small delay between requests to be respectful."""
        delay = random.uniform(self.MIN_DELAY_SECONDS, self.MAX_DELAY_SECONDS)
        await asyncio.sleep(delay)
        
    def _get_store_filter(self) -> Optional[set]:
        """Get merchant IDs to filter by, or None for all stores."""
        if not self.stores:
            return None
        
        store_ids = set()
        for store_key in self.stores:
            if store_key.lower() in CANADIAN_STORES:
                store_ids.add(CANADIAN_STORES[store_key.lower()].id)
        return store_ids if store_ids else None
    
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

    def _parse_flyer_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a flyer item from the API response."""
        try:
            name = item.get("name", "Unknown")
            merchant = item.get("merchant_name", "Unknown Store")
            
            # Skip if we've already seen this item from this store
            item_key = f"{name}|{merchant}"
            if item_key in self.seen_items:
                return None
            self.seen_items.add(item_key)
            
            # Parse prices
            current_price = item.get("current_price")
            original_price = item.get("original_price")
            
            if current_price is None:
                return None
                
            # Try to parse as float
            try:
                current_price = float(current_price) if current_price else 0.0
                original_price = float(original_price) if original_price else current_price
            except (ValueError, TypeError):
                return None
                
            if current_price <= 0:
                return None
            
            # Parse unit from post_price_text (e.g., "/lb", "/kg")
            post_price = item.get("post_price_text", "")
            unit = "each"
            if "/lb" in post_price.lower():
                unit = "lb"
            elif "/kg" in post_price.lower():
                unit = "kg"
            elif "/100" in post_price.lower():
                unit = "100g"
            elif "/l" in post_price.lower():
                unit = "L"
                
            # Determine category from L1/L2 taxonomy
            l1 = item.get("_L1", "")
            l2 = item.get("_L2", "")
            category = self._determine_category(l1, l2, name)
            
            # Get sale info if available
            sale_story = item.get("sale_story", "")
            
            # Parse loyalty points
            loyalty_info = self._parse_loyalty_points(sale_story)
            loyalty_program, loyalty_points = loyalty_info if loyalty_info else (None, None)

            return {
                "name": name,
                "category": category,
                "price": round(current_price, 2),
                "original_price": round(original_price, 2),
                "unit": unit,
                "store": merchant,
                "sale_info": sale_story,
                "loyalty_program": loyalty_program,
                "loyalty_points": loyalty_points,
                "image_url": item.get("clean_image_url", ""),
                "valid_from": item.get("valid_from", ""),
                "valid_to": item.get("valid_to", ""),
                "flyer_item_id": item.get("flyer_item_id", ""),
            }
            
        except Exception as e:
            print(f"Error parsing flyer item: {e}")
            return None
    
    def _parse_ecom_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse an e-commerce item from the API response."""
        try:
            name = item.get("name", "Unknown")
            merchant = item.get("merchant", "Unknown Store")
            
            item_key = f"{name}|{merchant}"
            if item_key in self.seen_items:
                return None
            self.seen_items.add(item_key)
            
            current_price = item.get("current_price")
            original_price = item.get("original_price")
            
            if current_price is None:
                return None
                
            try:
                current_price = float(current_price) if current_price else 0.0
                original_price = float(original_price) if original_price else current_price
            except (ValueError, TypeError):
                return None
                
            if current_price <= 0:
                return None
            
            return {
                "name": name,
                "category": "Grocery",  # ecom items don't have L1/L2
                "price": round(current_price, 2),
                "original_price": round(original_price, 2),
                "unit": "each",
                "store": merchant,
                "sale_info": "",
                "image_url": item.get("image_url", ""),
                "valid_from": "",
                "valid_to": "",
                "sku": item.get("sku", ""),
            }
            
        except Exception as e:
            print(f"Error parsing ecom item: {e}")
            return None
    
    def _determine_category(self, l1: str, l2: str, name: str) -> str:
        """Determine a simplified category from Flipp taxonomy."""
        name_lower = name.lower()
        l2_lower = l2.lower()
        
        # Meat & Poultry
        if any(x in name_lower for x in ["chicken", "beef", "pork", "turkey", "lamb", "sausage", "bacon", "ham"]):
            return "Meat & Poultry"
        if any(x in l2_lower for x in ["meat", "poultry"]):
            return "Meat & Poultry"
            
        # Seafood
        if any(x in name_lower for x in ["fish", "salmon", "shrimp", "tuna", "crab", "lobster", "seafood"]):
            return "Seafood"
            
        # Fruits & Vegetables
        if any(x in name_lower for x in ["apple", "banana", "orange", "grape", "berry", "melon", "mango"]):
            return "Fruits"
        if any(x in name_lower for x in ["lettuce", "tomato", "carrot", "potato", "onion", "pepper", "broccoli", "spinach"]):
            return "Vegetables"
        if "fruit" in l2_lower or "vegetable" in l2_lower:
            return "Fruits & Vegetables"
            
        # Dairy & Eggs
        if any(x in name_lower for x in ["milk", "cheese", "yogurt", "cream", "butter", "egg"]):
            return "Dairy & Eggs"
        if "dairy" in l2_lower:
            return "Dairy & Eggs"
            
        # Bakery
        if any(x in name_lower for x in ["bread", "bagel", "muffin", "croissant", "bun", "roll"]):
            return "Bakery"
            
        # Pantry
        if any(x in name_lower for x in ["rice", "pasta", "cereal", "sauce", "soup", "can"]):
            return "Pantry"
            
        # Beverages
        if any(x in name_lower for x in ["juice", "water", "coffee", "tea", "soda", "pop", "drink"]):
            return "Beverages"
            
        # Frozen
        if any(x in name_lower for x in ["frozen", "ice cream"]):
            return "Frozen"
            
        # Snacks
        if any(x in name_lower for x in ["chip", "cookie", "cracker", "chocolate", "candy", "snack"]):
            return "Snacks"
            
        return "Grocery"
    
    async def search(
        self, 
        query: str,
        session: aiohttp.ClientSession
    ) -> List[Dict[str, Any]]:
        """
        Search for items matching a query.
        
        Args:
            query: Search term
            session: aiohttp session for making requests
            
        Returns:
            List of parsed items
        """
        url = f"{self.BASE_URL}/items/search"
        params = {
            "locale": self.locale,
            "postal_code": self.postal_code,
            "q": query
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        store_filter = self._get_store_filter()
        results = []
        
        try:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status != 200:
                    print(f"Search API returned {response.status} for query '{query}'")
                    return []
                    
                data = await response.json()
                
                # Process flyer items (traditional flyer deals)
                flyer_items = data.get("items", [])
                for item in flyer_items:
                    merchant_id = item.get("merchant_id")
                    merchant_name = item.get("merchant_name", "").lower()

                    # Filter by merchant ID if in our list, or fallback to name matching
                    if store_filter:
                        if merchant_id not in store_filter:
                            # Fallback: check if the merchant name matches any of our requested stores
                            if not self.stores or not any(s.lower() in merchant_name for s in self.stores):
                                continue

                    parsed = self._parse_flyer_item(item)
                    if parsed:
                        results.append(parsed)
                        
                # Process e-commerce items (online store items)
                ecom_items = data.get("ecom_items", [])
                for item in ecom_items:
                    merchant_id = item.get("merchant_id")
                    merchant_name = item.get("merchant", "").lower()

                    if store_filter:
                        if merchant_id not in store_filter:
                            if not self.stores or not any(s.lower() in merchant_name for s in self.stores):
                                continue

                    parsed = self._parse_ecom_item(item)
                    if parsed:
                        results.append(parsed)
                        
        except Exception as e:
            print(f"Error searching for '{query}': {e}")
            
        return results
    
    async def scrape(
        self, 
        limit: int = 100,
        search_terms: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Scrape grocery deals from Flipp.
        
        Args:
            limit: Maximum number of items to return
            search_terms: Custom search terms (uses defaults if None)
            
        Returns:
            List of grocery deal items
        """
        terms = search_terms or self.DEFAULT_SEARCH_TERMS
        
        store_names = "all stores"
        if self.stores:
            store_names = ", ".join(
                CANADIAN_STORES[s].name for s in self.stores if s in CANADIAN_STORES
            )
        
        print("Starting Flipp scraper...")
        print(f"Location: {self.postal_code}")
        print(f"Stores: {store_names}")
        print(f"Search terms: {len(terms)}")
        
        self.items = []
        self.seen_items = set()
        
        async with aiohttp.ClientSession() as session:
            for i, term in enumerate(terms):
                if len(self.items) >= limit:
                    print(f"Reached limit of {limit} items, stopping.")
                    break
                    
                print(f"[{i+1}/{len(terms)}] Searching: '{term}'...")
                
                results = await self.search(term, session)
                self.items.extend(results)
                
                print(f"  Found {len(results)} items (total: {len(self.items)})")
                
                # Rate limit between requests
                if i < len(terms) - 1:
                    await self._random_delay()
        
        # Deduplicate and limit
        final_items = self.items[:limit]
        
        print("\nScraping complete!")
        print(f"Total unique items: {len(final_items)}")
        
        # Summary by store
        store_counts: Dict[str, int] = {}
        for item in final_items:
            store = item.get("store", "Unknown")
            store_counts[store] = store_counts.get(store, 0) + 1
            
        print("\nItems by store:")
        for store, count in sorted(store_counts.items(), key=lambda x: -x[1]):
            print(f"  {store}: {count}")
            
        return final_items


async def main():
    """Test the Flipp scraper."""
    # Scrape from specific stores (Metro, Maxi, Super C)
    scraper = FlippScraper(
        postal_code="H4T1V6",
        stores=["metro", "maxi", "super_c", "walmart"]
    )
    
    items = await scraper.scrape(limit=50)
    
    print("\n" + "="*50)
    print("Sample items:")
    print("="*50)
    
    for item in items[:10]:
        savings = item["original_price"] - item["price"]
        savings_pct = (savings / item["original_price"] * 100) if item["original_price"] > 0 else 0
        
        print(f"\n{item['name']}")
        print(f"  Store: {item['store']}")
        print(f"  Price: ${item['price']:.2f} (was ${item['original_price']:.2f})")
        if savings > 0:
            print(f"  Savings: ${savings:.2f} ({savings_pct:.0f}% off)")
        print(f"  Category: {item['category']}")
        if item.get('sale_info'):
            print(f"  Sale: {item['sale_info']}")


if __name__ == "__main__":
    asyncio.run(main())
