import pytest
from app.services.ingredient_matching_service import IngredientMatchingService

@pytest.fixture
def matcher():
    return IngredientMatchingService()

def test_normalization(matcher):
    assert matcher.normalize("1kg Chicken Breast") == "chicken breast"
    assert matcher.normalize("Organic Fresh Spinach (500g)") == "spinach"
    assert matcher.normalize("2% Milk, 2L") == "milk"
    assert matcher.normalize("Extra Virgin Olive Oil") == "virgin olive oil"

def test_exact_match(matcher):
    assert matcher.is_match("Chicken Breast", "chicken breast") is True

def test_substring_match(matcher):
    assert matcher.is_match("Chicken", "Chicken Breast") is True
    assert matcher.is_match("1kg Chicken Breast", "Chicken") is True

def test_fuzzy_match(matcher):
    assert matcher.is_match("Breast of Chicken", "Chicken Breast") is True
    assert matcher.is_match("Ground Beef", "Beef Ground") is True

def test_no_match(matcher):
    assert matcher.is_match("Chicken", "Beef") is False
    assert matcher.is_match("Apples", "Oranges") is False

def test_synonym_match(matcher):
    assert matcher.is_match("butter", "margarine") is True
    assert matcher.is_match("margarine", "butter") is True

def test_bilingual_matching(matcher):
    # Quebec flyer French terms vs Recipe English terms
    assert matcher.is_match("Poitrine de poulet désossée", "Chicken Breast") is True
    assert matcher.is_match("Boeuf haché mi-maigre", "Ground Beef") is True
    assert matcher.is_match("Filet de porc", "Pork Tenderloin") is True
    assert matcher.is_match("Pommes de terre", "Potatoes") is True
    assert matcher.is_match("Lait 2%", "Milk") is True

def test_unit_conversions(matcher):
    # Mass conversions
    qty_kg, exact = matcher.convert_quantity(1.0, "kg", "lb")
    assert round(qty_kg, 2) == 2.20
    assert exact is True

    qty_g, exact = matcher.convert_quantity(500, "g", "kg")
    assert qty_g == 0.5
    assert exact is True

    # Volume conversions
    qty_ml, exact = matcher.convert_quantity(2.0, "cups", "ml")
    assert qty_ml == 480.0
    assert exact is True

    # Cost calculation: $10.00/kg, recipe requires 500g -> $5.00
    cost = matcher.calculate_cost(price=10.0, price_unit="kg", required_qty=500, required_unit="g")
    assert cost == 5.00

def test_find_best_match(matcher):
    candidates = ["Chicken Breast", "Ground Beef", "Fresh Spinach", "Whole Milk"]
    best, score = matcher.find_best_match("1kg Chicken", candidates)
    assert best == "Chicken Breast"
    assert score >= 90

    best, score = matcher.find_best_match("Beef", candidates)
    assert best == "Ground Beef"

    # Test threshold
    assert matcher.find_best_match("Apples", candidates, threshold=90) is None
