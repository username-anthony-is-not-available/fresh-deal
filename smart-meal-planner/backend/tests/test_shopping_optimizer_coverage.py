"""Extra coverage for app/services/shopping_optimizer.py.

Covers the paths the existing suite never exercises: recipe-load failure,
the sync/async generate_shopping_list flows, both price-lookup paths,
_calculate_options conversions, and the _optimize_routes consolidation /
max-stores branches. Uses a fake session and fabricated priced items so no
database or network is involved.
"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.all_models import Deal, PantryItem, Product, Store
from app.services.shopping_optimizer import ShoppingListOptimizer


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def optimizer(mock_session):
    return ShoppingListOptimizer(mock_session)


def _product(**kw):
    kw.setdefault("id", 1)
    kw.setdefault("name", "Chicken Breast")
    kw.setdefault("category", "Meat")
    kw.setdefault("unit_type", "kg")
    return Product(**kw)


def _deal(**kw):
    kw.setdefault("id", 1)
    kw.setdefault("product_id", 1)
    kw.setdefault("store_id", 1)
    kw.setdefault("price", 5.0)
    kw.setdefault("discount_pct", None)
    kw.setdefault("valid_from", date.today())
    kw.setdefault("valid_until", date.today())
    return Deal(**kw)


def _store(**kw):
    kw.setdefault("id", 1)
    kw.setdefault("name", "Walmart")
    kw.setdefault("chain", "Walmart")
    kw.setdefault("postal_code", "H1H1H1")
    return Store(**kw)


def _fake_result(rows):
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


def _user(**kw):
    return SimpleNamespace(id=kw.get("id", 1), household_size=kw.get("household_size", 4))


# ---------------------------------------------------------------------------
# _load_recipes / get_recipe_by_id
# ---------------------------------------------------------------------------

def test_load_recipes_failure_returns_empty(mock_session, monkeypatch):
    def _boom(*args, **kwargs):
        raise OSError("no file")

    monkeypatch.setattr("builtins.open", _boom)
    optimizer = ShoppingListOptimizer(mock_session)
    assert optimizer.recipes == []


def test_get_recipe_by_id_hit_and_miss(optimizer):
    recipe = optimizer.get_recipe_by_id("recipe_001")
    assert recipe is not None
    assert recipe["id"] == "recipe_001"
    assert optimizer.get_recipe_by_id("no-such-recipe") is None


# ---------------------------------------------------------------------------
# _consolidate_ingredients
# ---------------------------------------------------------------------------

def test_consolidate_legacy_days_format_scales_and_merges_units(optimizer):
    plan = {
        "days": [
            {"meals": [
                {"ingredients": [
                    {"item": "Chicken Breast", "quantity": 1.0, "unit": "kg"},
                    {"item": "Chicken Breast", "quantity": 1.0, "unit": "lb"},
                    {"item": "Milk", "quantity": 1.0, "unit": "L"},
                    {"item": "Milk", "quantity": 500.0, "unit": "ml"},
                ]},
            ]},
        ]
    }
    # household 8 -> scale 2
    out = optimizer._consolidate_ingredients(plan, 8)
    assert out[("Chicken Breast", "kg")]["qty"] == pytest.approx(2.0 + 2.0 * 0.453592, abs=0.01)
    # 1.0 L * 2 = 2.0 L, plus 500ml * 2 = 1000ml -> 1.0 L merged in
    assert out[("Milk", "L")]["qty"] == pytest.approx(3.0)
    assert ("Milk", "ml") not in out


def test_consolidate_new_format_breakfast_lunch_dinner(optimizer):
    plan = {
        "meal_plan": [
            {
                "breakfast": {"ingredients": [{"item": "Oats", "quantity": 0.5, "unit": "kg"}]},
                "lunch": {"ingredients": [{"item": "Oats", "quantity": 0.5, "unit": "kg"}]},
                "dinner": None,
            }
        ]
    }
    out = optimizer._consolidate_ingredients(plan, 4)
    assert out[("Oats", "kg")]["qty"] == pytest.approx(1.0)


def test_consolidate_lookup_by_recipe_id(optimizer):
    plan = {"days": [{"meals": [{"id": "recipe_001"}]}]}
    out = optimizer._consolidate_ingredients(plan, 4)
    assert ("Chicken Breast (Boneless)", "kg") in out
    assert out[("Chicken Breast (Boneless)", "kg")]["qty"] == pytest.approx(0.5)


def test_consolidate_unknown_recipe_id_skipped(optimizer):
    plan = {"days": [{"meals": [{"recipe_id": "does-not-exist"}]}]}
    assert optimizer._consolidate_ingredients(plan, 4) == {}


def test_consolidate_lb_to_kg_merge_and_rounding(optimizer):
    plan = {
        "days": [
            {"meals": [
                {"ingredients": [
                    {"item": "Beef", "quantity": 1.0, "unit": "lb"},
                    {"item": "Beef", "quantity": 1.0, "unit": "kg"},
                    {"item": "Sugar", "quantity": 0.333, "unit": "kg"},
                ]},
            ]},
        ]
    }
    out = optimizer._consolidate_ingredients(plan, 4)
    assert out[("Beef", "lb")]["qty"] == pytest.approx(1.0 + 2.20462, abs=0.01)
    assert out[("Sugar", "kg")]["qty"] == 0.33


# ---------------------------------------------------------------------------
# _subtract_pantry
# ---------------------------------------------------------------------------

def test_subtract_pantry_partial_and_unit_conversion(optimizer):
    consolidated = {("flour", "kg"): {"qty": 2.0, "unit": "kg"}}
    pantry = [PantryItem(user_id=1, name="flour", quantity=500.0, unit="g")]
    optimizer._subtract_pantry(consolidated, pantry)
    assert consolidated[("flour", "kg")]["qty"] == pytest.approx(1.5)


def test_subtract_pantry_skips_empty_name_and_zero_qty(optimizer):
    consolidated = {("rice", "kg"): {"qty": 1.0, "unit": "kg"}}
    pantry = [
        PantryItem(user_id=1, name="", quantity=5.0, unit="kg"),
        PantryItem(user_id=1, name="rice", quantity=0.0, unit="kg"),
        PantryItem(user_id=1, name=None, quantity=5.0, unit="kg"),
    ]
    optimizer._subtract_pantry(consolidated, pantry)
    assert consolidated[("rice", "kg")]["qty"] == 1.0


def test_subtract_pantry_over_covering_removes_item(optimizer):
    consolidated = {("salt", "g"): {"qty": 10.0, "unit": "g"}}
    pantry = [PantryItem(user_id=1, name="salt", quantity=1.0, unit="kg")]
    optimizer._subtract_pantry(consolidated, pantry)
    assert consolidated == {}


# ---------------------------------------------------------------------------
# generate_shopping_list (sync) and generate_shopping_list_async
# ---------------------------------------------------------------------------

def test_generate_shopping_list_sync(optimizer, mock_session, monkeypatch):
    pantry = [PantryItem(user_id=1, name="rice", quantity=1.0, unit="kg")]
    mock_session.exec.return_value.all.return_value = pantry
    options = [
        {"store_id": 1, "store_name": "Walmart", "chain": "Walmart",
         "price": 2.0, "discount_pct": None, "unit_type": "kg", "category": "Grocery"}
    ]
    monkeypatch.setattr(
        optimizer, "_find_prices_for_ingredient_sync", lambda *a: options
    )
    plan = {"days": [{"meals": [{"ingredients": [
        {"item": "Rice", "quantity": 2.0, "unit": "kg"},
    ]}]}]}
    result = optimizer.generate_shopping_list(_user(), plan, strategy="min_cost")
    assert result["strategy"] == "min_cost"
    assert result["total_items_count"] == 1
    assert result["recommended_stores"][0]["store"] == "Walmart"
    assert result["recommended_stores"][0]["subtotal"] == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_generate_shopping_list_async(optimizer, mock_session, monkeypatch):
    mock_session.execute = AsyncMock(
        return_value=_fake_result(
            [PantryItem(user_id=1, name="rice", quantity=0.5, unit="kg")]
        )
    )
    options = [
        {"store_id": 2, "store_name": "Metro", "chain": "Metro",
         "price": 3.0, "discount_pct": 10.0, "unit_type": "kg", "category": "Grocery"}
    ]

    async def _fake_find(name, unit):
        return options

    monkeypatch.setattr(optimizer, "_find_prices_for_ingredient_async", _fake_find)
    plan = {"days": [{"meals": [{"ingredients": [
        {"item": "Rice", "quantity": 1.0, "unit": "kg"},
    ]}]}]}
    result = await optimizer.generate_shopping_list_async(_user(), plan, strategy="min_cost")
    assert result["recommended_stores"][0]["store"] == "Metro"
    # 0.5 kg pantry subtracted from 1.0 kg needed -> 0.5 kg * 3.0 = 1.50
    assert result["recommended_stores"][0]["subtotal"] == pytest.approx(1.5)
    assert result["total_savings"] == pytest.approx(0.17, abs=0.01)


# ---------------------------------------------------------------------------
# _find_prices_for_ingredient_sync / _find_prices_for_ingredient_async
# ---------------------------------------------------------------------------

def test_find_prices_sync_empty_normalized_name(optimizer):
    optimizer.ingredient_matcher = MagicMock()
    optimizer.ingredient_matcher.normalize.return_value = ""
    assert optimizer._find_prices_for_ingredient_sync("!!!", "kg") == []


def test_find_prices_sync_no_matching_product(optimizer, mock_session):
    optimizer.ingredient_matcher = MagicMock()
    optimizer.ingredient_matcher.normalize.side_effect = lambda s: s.lower()
    optimizer.ingredient_matcher.is_match.return_value = False
    mock_session.exec.return_value.all.return_value = [_product()]
    assert optimizer._find_prices_for_ingredient_sync("Chicken Breast", "kg") == []


def test_find_prices_sync_best_product_and_unit_conversion(optimizer, mock_session):
    optimizer.ingredient_matcher = MagicMock()
    optimizer.ingredient_matcher.normalize.side_effect = lambda s: s.lower()
    optimizer.ingredient_matcher.is_match.side_effect = lambda a, b: True
    candidates = [_product(id=1, name="Chicken Breast"), _product(id=2, name="Chicken")]
    deal = _deal(product_id=1, store_id=1, price=4.0, discount_pct=20.0)
    store = _store()
    mock_session.exec.side_effect = [
        MagicMock(all=MagicMock(return_value=candidates)),
        MagicMock(all=MagicMock(return_value=[deal])),
        MagicMock(all=MagicMock(return_value=[store])),
    ]
    options = optimizer._find_prices_for_ingredient_sync("Chicken Breast", "lb")
    assert len(options) == 1
    # product unit kg -> required lb: price * 0.453592
    assert options[0]["price"] == pytest.approx(4.0 * 0.453592)
    assert options[0]["discount_pct"] == 20.0
    assert options[0]["store_name"] == "Walmart"


def test_find_prices_sync_short_words_fallback_stmt(optimizer, mock_session):
    optimizer.ingredient_matcher = MagicMock()
    optimizer.ingredient_matcher.normalize.return_value = "ox"
    optimizer.ingredient_matcher.is_match.return_value = False
    mock_session.exec.return_value.all.return_value = []
    assert optimizer._find_prices_for_ingredient_sync("ox", "kg") == []


@pytest.mark.asyncio
async def test_find_prices_async_happy_path(optimizer, mock_session):
    optimizer.ingredient_matcher = MagicMock()
    optimizer.ingredient_matcher.normalize.side_effect = lambda s: s.lower()
    optimizer.ingredient_matcher.is_match.return_value = True
    product = _product(unit_type="lb")
    deal = _deal(price=2.0)
    store = _store()
    mock_session.execute = AsyncMock(
        side_effect=[
            _fake_result([product]),
            _fake_result([deal]),
            _fake_result([store]),
        ]
    )
    options = await optimizer._find_prices_for_ingredient_async("Chicken Breast", "kg")
    assert len(options) == 1
    # product unit lb -> required kg: price * 2.20462
    assert options[0]["price"] == pytest.approx(2.0 * 2.20462)


@pytest.mark.asyncio
async def test_find_prices_async_no_product(optimizer, mock_session):
    optimizer.ingredient_matcher = MagicMock()
    optimizer.ingredient_matcher.normalize.side_effect = lambda s: s.lower()
    optimizer.ingredient_matcher.is_match.return_value = True
    mock_session.execute = AsyncMock(return_value=_fake_result([]))
    assert await optimizer._find_prices_for_ingredient_async("Nope", "kg") == []


@pytest.mark.asyncio
async def test_find_prices_async_empty_normalized(optimizer):
    optimizer.ingredient_matcher = MagicMock()
    optimizer.ingredient_matcher.normalize.return_value = ""
    assert await optimizer._find_prices_for_ingredient_async("!!!", "kg") == []


@pytest.mark.asyncio
async def test_find_prices_async_short_words_fallback_stmt(optimizer, mock_session):
    optimizer.ingredient_matcher = MagicMock()
    optimizer.ingredient_matcher.normalize.return_value = "ox"
    optimizer.ingredient_matcher.is_match.return_value = False
    mock_session.execute = AsyncMock(return_value=_fake_result([]))
    assert await optimizer._find_prices_for_ingredient_async("ox", "kg") == []


# ---------------------------------------------------------------------------
# _calculate_options
# ---------------------------------------------------------------------------

def test_calculate_options_skips_missing_store_and_converts(optimizer):
    deals = [
        SimpleNamespace(store_id=99, price=1.0, discount_pct=None),
        SimpleNamespace(store_id=1, price=2.0, discount_pct=50.0),
    ]
    store_map = {1: SimpleNamespace(id=1, name="Metro", chain="Metro")}
    product = SimpleNamespace(unit_type="kg", category="Dairy")
    options = optimizer._calculate_options(deals, store_map, product, "lb")
    assert len(options) == 1
    assert options[0]["price"] == pytest.approx(2.0 * 0.453592)
    assert options[0]["discount_pct"] == 50.0


def test_calculate_options_lb_to_kg(optimizer):
    deals = [SimpleNamespace(store_id=1, price=3.0, discount_pct=None)]
    store_map = {1: SimpleNamespace(id=1, name="IGA", chain="IGA")}
    product = SimpleNamespace(unit_type="lb", category="Meat")
    options = optimizer._calculate_options(deals, store_map, product, "kg")
    assert options[0]["price"] == pytest.approx(3.0 * 2.20462)


# ---------------------------------------------------------------------------
# _optimize_routes extra branches
# ---------------------------------------------------------------------------

def _priced(ingredient, qty, unit, options):
    return {"ingredient": ingredient, "quantity": qty, "unit": unit, "options": options}


def _opt(store, price, discount=None):
    return {"store_id": 1, "store_name": store, "chain": store,
            "price": price, "discount_pct": discount, "category": "Grocery"}


def test_optimize_routes_empty_priced_items(optimizer):
    result = optimizer._optimize_routes([], strategy="min_cost")
    assert result["total_cost"] == 0
    assert result["total_items_count"] == 0
    assert result["trip_efficiency"] == 0
    assert result["recommended_stores"] == []


def test_optimize_routes_discount_regular_costs(optimizer):
    priced = [_priced("Cheese", 2, "kg", [_opt("Metro", 10.0, discount=50.0)])]
    result = optimizer._optimize_routes(priced, strategy="min_cost")
    store = result["recommended_stores"][0]
    assert store["subtotal"] == 20.0
    # regular 20.0 per kg * 2 = 40, savings 20
    assert store["savings"] == pytest.approx(20.0)
    assert result["total_regular_cost"] == pytest.approx(40.0)


def test_optimize_routes_max_stores_cap_enforced(optimizer):
    priced = [
        _priced("A", 1, "kg", [_opt("Store A", 1.0), _opt("Store B", 5.0), _opt("Store C", 5.0)]),
        _priced("B", 1, "kg", [_opt("Store A", 5.0), _opt("Store B", 1.0), _opt("Store C", 5.0)]),
        _priced("C", 1, "kg", [_opt("Store A", 5.0), _opt("Store B", 5.0), _opt("Store C", 1.0)]),
    ]
    result = optimizer._optimize_routes(
        priced, strategy="min_cost", max_stores=2, travel_cost_per_stop=0.01
    )
    assert len(result["recommended_stores"]) <= 2
    assert result["max_stores_limit"] == 2


def test_optimize_routes_consolidate_when_single_store_missing_least(optimizer):
    # No store carries everything; min_cost picks 2 stores, consolidation must
    # pick the least-missing single store instead of crashing.
    priced = [
        _priced("A", 1, "kg", [_opt("Store A", 1.0), _opt("Store B", 2.0)]),
        _priced("B", 1, "kg", [_opt("Store B", 1.0)]),
        _priced("C", 1, "kg", [_opt("Store A", 1.0)]),
    ]
    result = optimizer._optimize_routes(
        priced, strategy="min_cost", travel_cost_per_stop=50.0
    )
    assert result["recommended_stores"]
    assert result["total_items_count"] == 3


def test_optimize_routes_convenience_prefers_complete_store(optimizer):
    priced = [
        _priced("A", 1, "kg", [_opt("Store A", 1.0), _opt("Store B", 0.9)]),
        _priced("B", 1, "kg", [_opt("Store A", 1.0)]),
    ]
    result = optimizer._optimize_routes(priced, strategy="convenience")
    assert result["recommended_stores"][0]["store"] == "Store A"


def test_optimize_routes_detailed_comparison_none_price(optimizer):
    priced = [
        _priced("A", 2, "kg", [_opt("Store A", 1.0)]),
        _priced("B", 1, "kg", [_opt("Store B", 4.0)]),
    ]
    result = optimizer._optimize_routes(priced, strategy="min_cost")
    detail_b = next(d for d in result["detailed_comparison"] if d["ingredient"] == "B")
    assert detail_b["prices"]["Store A"] is None
    assert detail_b["prices"]["Store B"] == 4.0
    assert result["all_stores"] == ["Store A", "Store B"]


def test_optimize_routes_unmatched_item_listed(optimizer):
    priced = [
        _priced("Milk", 1, "L", [_opt("Store A", 2.0)]),
        _priced("Rare Spice", 1, "g", []),
    ]
    result = optimizer._optimize_routes(priced, strategy="min_cost")
    assert result["unmatched_items"] == ["Rare Spice"]
    assert result["trip_efficiency"] == 50.0


def test_optimize_routes_convenience_preferred_store_bonus(optimizer):
    priced = [
        _priced("Milk", 1, "L", [_opt("Store A", 2.5), _opt("Store B", 2.0)]),
    ]
    result = optimizer._optimize_routes(
        priced, strategy="convenience", preferred_stores=["Store A"]
    )
    assert result["recommended_stores"][0]["store"] == "Store A"


def test_optimize_routes_max_stores_cap_keeps_orphan_item_in_top_store(optimizer):
    priced = [
        _priced("A", 1, "kg", [_opt("Store A", 1.0), _opt("Store B", 5.0), _opt("Store C", 5.0)]),
        _priced("B", 1, "kg", [_opt("Store A", 5.0), _opt("Store B", 1.0), _opt("Store C", 5.0)]),
        # Only available at Store C, which will not be a top store by spend.
        _priced("C", 1, "kg", [_opt("Store C", 1.0)]),
    ]
    result = optimizer._optimize_routes(
        priced, strategy="min_cost", max_stores=2, travel_cost_per_stop=0.01
    )
    assert len(result["recommended_stores"]) <= 2
    names = {s["store"] for s in result["recommended_stores"]}
    assert "Store C" not in names
    all_items = [i["name"] for s in result["recommended_stores"] for i in s["items"]]
    assert "C" in all_items
