import sys
sys.path.append('smart-meal-planner/backend')
from app.agents.scrapers.base_scraper import BaseScraper

class TestScraper(BaseScraper):
    async def _scrape_page(self, page, limit):
        return []

scraper = TestScraper()
test_prices = [
    "2 pour 5.00$",
    "Buy 1 get 1 free",
    "2nd at 50% off",
    "Save $2.00",
    "1,99$ ch.",
    "0.88$ l'unité",
    "Prix membre 2,99$",
    "Rabais de 3$",
    "3.99$ (Save $1.00)"
]

print("--- Price Parsing ---")
for p in test_prices:
    print(f"Price: {p:20} -> Parsed: {scraper._parse_price(p)}")

print("\n--- Discount Parsing ---")
for p in test_prices:
    print(f"Discount: {p:20} -> Parsed: {scraper._parse_discount(p)}")

print("\n--- Unit Extraction ---")
test_units = [
    "Apples 2.99$ / lb",
    "Potatoes 5$ / sac",
    "Milk 2L",
    "Cheese 500g",
    "Cucumber 1.25$ ch.",
    "1.50$ l'unité"
]
for u in test_units:
    print(f"Unit: {u:20} -> Extracted: {scraper._extract_unit(u)}")
