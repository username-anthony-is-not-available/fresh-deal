import pytest
from datetime import date
from src.scrapers.BaseScraper import BaseScraper

class MockScraper(BaseScraper):
    async def fetch_deals(self, page, limit):
        return []
    def parse_html(self, html_content):
        return []

@pytest.fixture
def scraper():
    return MockScraper()

def test_parse_price(scraper):
    assert scraper._parse_price("$4.99") == 4.99
    assert scraper._parse_price("2 for $5.00") == 2.50
    assert scraper._parse_price("99¢") == 0.99
    assert scraper._parse_price("3 / $10.00") == 3.33
    assert scraper._parse_price("Save $1.00 4.99$") == 4.99
    assert scraper._parse_price("None") is None
    # Test reverse multi-buy if supported
    assert scraper._parse_price("$5.00 / 2") == 2.50

def test_extract_unit(scraper):
    assert scraper._extract_unit("Apples 2kg") == "kg"
    assert scraper._extract_unit("Beef /lb") == "lb"
    assert scraper._extract_unit("Milk 1L") == "L"
    assert scraper._extract_unit("Yogurt 100g") == "100g"
    assert scraper._extract_unit("Cereal 500g") == "g"
    assert scraper._extract_unit("Juice 500ml") == "ml"
    assert scraper._extract_unit("Something else") == "each"

def test_parse_flyer_dates(scraper):
    # English format
    start, end = scraper._parse_flyer_dates("from Jan 1 to Jan 7, 2024")
    assert start == date(2024, 1, 1)
    assert end == date(2024, 1, 7)

    # French format
    start, end = scraper._parse_flyer_dates("du 1 janv. au 7 janv. 2024")
    assert start == date(2024, 1, 1)
    assert end == date(2024, 1, 7)

def test_categorize_product(scraper):
    assert scraper._categorize_product("Orange Juice") == "Beverages"
    assert scraper._categorize_product("Chicken Breast") == "Meat & Poultry"
    assert scraper._categorize_product("Gala Apple") == "Fruits"
    assert scraper._categorize_product("Toilet Paper") == "Household"
    assert scraper._categorize_product("Unknown Item") == "Grocery"

def test_parse_loyalty_points(scraper):
    assert scraper._parse_loyalty_points("Get 500 PC Optimum points") == ("PC Optimum", 500)
    assert scraper._parse_loyalty_points("1,000 Moi points") == ("Moi", 1000)
    assert scraper._parse_loyalty_points("Scene+ 250 points") == ("Scene+", 250)
    assert scraper._parse_loyalty_points("No points here") is None

def test_calculate_original_price(scraper):
    assert scraper._calculate_original_price(8.0, 20.0) == 10.0
    assert scraper._calculate_original_price(5.0, 0.0) == 5.0
    assert scraper._calculate_original_price(5.0, None) == 5.0
    assert scraper._calculate_original_price(None, 20.0) == 0.0

def test_parse_discount(scraper):
    assert scraper._parse_discount("Save 20%") == 20.0
    assert scraper._parse_discount("No discount") is None

def test_parse_flyer_dates_more_formats(scraper):
    # Additional date formats
    assert scraper._parse_flyer_dates("du 1 au 7 janv. 2024") == (date(2024, 1, 1), date(2024, 1, 7))
    assert scraper._parse_flyer_dates("from 1 to 7 Jan. 2024") == (date(2024, 1, 1), date(2024, 1, 7))
    assert scraper._parse_flyer_dates("du 1 janv. 2024 au 7 janv. 2024") == (date(2024, 1, 1), date(2024, 1, 7))
    assert scraper._parse_flyer_dates(None) == (None, None)

def test_extract_unit_more_units(scraper):
    assert scraper._extract_unit("Beef /kg") == "kg"
    assert scraper._extract_unit("Sugar bag") == "sac/box"
    assert scraper._extract_unit("Eggs pack") == "pack"
    assert scraper._extract_unit("Soda case") == "case"
    assert scraper._extract_unit("Milk 100 ml") == "ml"
    assert scraper._extract_unit("Oil 1 L") == "L"
    assert scraper._extract_unit("per 100 g") == "100g"

def test_categorize_product_more_categories(scraper):
    assert scraper._categorize_product("Chips") == "Snacks"
    assert scraper._categorize_product("Creton") == "Deli"
    assert scraper._categorize_product("Salmon") == "Seafood"
    assert scraper._categorize_product("Tomato") == "Vegetables"
    assert scraper._categorize_product("Milk") == "Dairy & Eggs"
    assert scraper._categorize_product("Bread") == "Bakery"
    assert scraper._categorize_product("Rice") == "Pantry"
    assert scraper._categorize_product("Hummus") == "International"
    assert scraper._categorize_product("Frozen Pizza") == "Frozen"
    assert scraper._categorize_product("Shampoo") == "Personal Care"

def test_parse_price_multi_buy_ea(scraper):
    assert scraper._parse_price("2 / 5.00 ea.") == 2.50
    assert scraper._parse_price("5.00 / 2 ea.") == 2.50
    assert scraper._parse_price("1.99 lb") == 1.99
    assert scraper._parse_price("1.99/lb") == 1.99
