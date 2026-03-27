
import pytest
from app.services.ingredient_matching_service import IngredientMatchingService

@pytest.fixture
def matcher():
    return IngredientMatchingService()

def test_normalization(matcher):
    assert matcher.normalize("1kg Chicken Breast") == "chicken breast"
    assert matcher.normalize("Organic Fresh Spinach (500g)") == "spinach"
    assert matcher.normalize("2% Milk, 2L") == "milk" # Wait, 2% might be tricky
    assert matcher.normalize("Extra Virgin Olive Oil") == "virgin olive oil" # 'extra' is filler

def test_exact_match(matcher):
    assert matcher.is_match("Chicken Breast", "chicken breast") is True

def test_substring_match(matcher):
    assert matcher.is_match("Chicken", "Chicken Breast") is True
    assert matcher.is_match("1kg Chicken Breast", "Chicken") is True

def test_fuzzy_match(matcher):
    # token_set_ratio should handle this
    assert matcher.is_match("Breast of Chicken", "Chicken Breast") is True
    assert matcher.is_match("Ground Beef", "Beef Ground") is True

def test_no_match(matcher):
    assert matcher.is_match("Chicken", "Beef") is False
    assert matcher.is_match("Apples", "Oranges") is False

def test_synonym_match(matcher):
    # Based on substitutions.json: "butter": ["margarine", ...]
    assert matcher.is_match("butter", "margarine") is True
    assert matcher.is_match("margarine", "butter") is True

def test_find_best_match(matcher):
    candidates = ["Chicken Breast", "Ground Beef", "Fresh Spinach", "Whole Milk"]
    best, score = matcher.find_best_match("1kg Chicken", candidates)
    assert best == "Chicken Breast"
    assert score >= 90

    best, score = matcher.find_best_match("Beef", candidates)
    assert best == "Ground Beef"

    # Test threshold
    assert matcher.find_best_match("Apples", candidates, threshold=90) is None
