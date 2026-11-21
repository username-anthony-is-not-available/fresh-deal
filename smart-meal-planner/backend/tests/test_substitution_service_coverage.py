"""Coverage for app/services/substitution_service.py.

The service is pure logic over substitutions.json plus the ingredient
matcher. The class-level _substitutions cache is reset between tests so
each load path is exercised fresh.
"""

import json

import pytest

from app.services.substitution_service import SubstitutionService


@pytest.fixture(autouse=True)
def _reset_cache():
    SubstitutionService._substitutions = None
    yield
    SubstitutionService._substitutions = None


@pytest.fixture
def service(tmp_path):
    data = {
        "chicken breast": ["turkey breast", "tofu"],
        "butter": ["margarine"],
    }
    path = tmp_path / "subs.json"
    path.write_text(json.dumps(data))
    return SubstitutionService(filepath=str(path))


def test_load_substitutions_from_filepath(service):
    assert service._load_substitutions() == {
        "chicken breast": ["turkey breast", "tofu"],
        "butter": ["margarine"],
    }
    # Second call uses the cache.
    assert service._load_substitutions() is service._substitutions


def test_load_substitutions_missing_file_uses_fallback(tmp_path):
    service = SubstitutionService(filepath=str(tmp_path / "does-not-exist.json"))
    loaded = service._load_substitutions()
    # Falls back to app/data/substitutions.json shipped with the repo.
    assert isinstance(loaded, dict)
    assert len(loaded) > 0


def test_load_substitutions_all_missing_returns_empty(tmp_path, monkeypatch):
    service = SubstitutionService(filepath=str(tmp_path / "does-not-exist.json"))
    monkeypatch.setattr("builtins.open", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()))
    assert service._load_substitutions() == {}


def test_get_substitutions_matches_and_misses(service):
    result = service.get_substitutions(["Chicken Breast", "Unrelated Item"])
    assert "Chicken Breast" in result
    assert result["Chicken Breast"] == ["turkey breast", "tofu"]
    assert "Unrelated Item" not in result


def test_get_substitutions_empty_input(service):
    assert service.get_substitutions([]) == {}


def test_find_deal_driven_substitutions_recommends_swap(service):
    required = [{"item": "Chicken Breast"}, {"item": "Butter"}]
    deals = [
        {"product": "Turkey Breast", "price": 4.0, "regular_price": 8.0, "store": "Metro"},
    ]
    swaps = service.find_deal_driven_substitutions(required, deals)
    assert len(swaps) == 1
    swap = swaps[0]
    assert swap["original_ingredient"] == "Chicken Breast"
    assert swap["substitute_ingredient"] == "turkey breast"
    assert swap["deal_price"] == 4.0
    assert swap["deal_store"] == "Metro"
    assert swap["estimated_savings"] == 4.0
    assert "Chicken Breast" in swap["reason"]


def test_find_deal_driven_substitutions_skips_on_sale_ingredient(service):
    required = [{"name": "Chicken Breast"}]
    deals = [{"product": "Chicken Breast", "price": 3.0, "regular_price": 6.0}]
    assert service.find_deal_driven_substitutions(required, deals) == []


def test_find_deal_driven_substitutions_no_matching_deal(service):
    required = [{"item": "Butter"}]
    deals = [{"product": "Turkey Breast", "price": 4.0}]
    assert service.find_deal_driven_substitutions(required, deals) == []


def test_find_deal_driven_substitutions_regular_price_fallbacks(service):
    required = [{"item": "Chicken Breast"}]
    # No regular/original price: falls back to deal_price * 1.4.
    deals = [{"product": "Turkey Breast", "price": 5.0}]
    swaps = service.find_deal_driven_substitutions(required, deals)
    assert len(swaps) == 1
    assert swaps[0]["estimated_savings"] == pytest.approx(2.0)
    assert swaps[0]["deal_store"] == "active flyer"


def test_find_deal_driven_substitutions_minimum_savings_floor(service):
    required = [{"item": "Chicken Breast"}]
    deals = [{"product": "Turkey Breast", "price": 5.0, "original_price": 5.1}]
    swaps = service.find_deal_driven_substitutions(required, deals)
    assert swaps[0]["estimated_savings"] == 0.50


def test_find_deal_driven_substitutions_empty_inputs(service):
    assert service.find_deal_driven_substitutions([], []) == []
    assert service.find_deal_driven_substitutions([{"item": "Butter"}], []) == []
