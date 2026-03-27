
import pytest
from unittest.mock import MagicMock, patch
from app.services.shopping_optimizer import ShoppingListOptimizer
from app.models.all_models import User, PantryItem

@pytest.fixture
def mock_session():
    return MagicMock()

def test_consolidate_ingredients_basic(mock_session):
    optimizer = ShoppingListOptimizer(mock_session)
    optimizer.recipes = [
        {
            "id": "r1",
            "ingredients": [
                {"item": "Chicken", "quantity": 1, "unit": "kg"},
                {"item": "Salt", "quantity": 1, "unit": "tsp"}
            ]
        }
    ]

    plan_data = {
        "days": [
            {"meals": [{"id": "r1"}, {"id": "r1"}]}
        ]
    }

    # Household size 4 means scale = 1
    result = optimizer._consolidate_ingredients(plan_data, household_size=4)

    assert result[("Chicken", "kg")]["qty"] == 2.0
    assert result[("Salt", "tsp")]["qty"] == 2.0

def test_consolidate_ingredients_unit_conversion(mock_session):
    optimizer = ShoppingListOptimizer(mock_session)
    optimizer.recipes = [
        {
            "id": "r1",
            "ingredients": [{"item": "Chicken", "quantity": 1, "unit": "kg"}]
        },
        {
            "id": "r2",
            "ingredients": [{"item": "Chicken", "quantity": 2.20462, "unit": "lb"}]
        }
    ]

    plan_data = {
        "days": [
            {"meals": [{"id": "r1"}, {"id": "r2"}]}
        ]
    }

    result = optimizer._consolidate_ingredients(plan_data, household_size=4)

    # Expect roughly 2.0 kg (1kg + ~1kg converted from lb)
    # The logic converts lb to kg if existing is kg
    assert ("Chicken", "kg") in result
    assert 1.99 < result[("Chicken", "kg")]["qty"] < 2.01

def test_strategy_min_cost(mock_session):
    optimizer = ShoppingListOptimizer(mock_session)

    # Mock priced items
    priced_items = [
        {
            "ingredient": "Milk",
            "quantity": 1,
            "unit": "L",
            "options": [
                {"store_name": "Store A", "store_id": 1, "chain": "Chain A", "price": 2.00, "discount_pct": 0, "total_item_cost": 2.00, "category": "Dairy"},
                {"store_name": "Store B", "store_id": 2, "chain": "Chain B", "price": 1.50, "discount_pct": 0, "total_item_cost": 1.50, "category": "Dairy"}
            ]
        }
    ]

    result = optimizer._optimize_routes(priced_items, strategy="min_cost")
    store_b = result["recommended_stores"][0]

    assert store_b["store"] == "Store B"
    assert result["total_cost"] == 1.50
    assert store_b["items"][0]["category"] == "Dairy"

def test_single_store_comparison(mock_session):
    optimizer = ShoppingListOptimizer(mock_session)

    priced_items = [
        {
            "ingredient": "Milk",
            "quantity": 1,
            "unit": "L",
            "options": [
                {"store_name": "Store A", "store_id": 1, "chain": "Chain A", "price": 2.00, "discount_pct": 0},
                {"store_name": "Store B", "store_id": 2, "chain": "Chain B", "price": 1.50, "discount_pct": 0}
            ]
        },
        {
            "ingredient": "Bread",
            "quantity": 1,
            "unit": "Loaf",
            "options": [
                {"store_name": "Store A", "store_id": 1, "chain": "Chain A", "price": 3.00, "discount_pct": 0},
                # Store B doesn't have bread
            ]
        }
    ]

    result = optimizer._optimize_routes(priced_items, strategy="min_cost")

    # Check single store comparison
    comp = result["single_store_comparison"]
    store_a = next(s for s in comp if s["name"] == "Store A")
    store_b = next(s for s in comp if s["name"] == "Store B")

    assert store_a["total"] == 5.00
    assert store_b["total"] == 1.50
    assert store_a["items_count"] == 2
    assert store_b["items_count"] == 1
    # Check that store_a is ranked higher (comes first) because it has no missing items
    assert comp[0]["name"] == "Store A"

def test_pantry_exclusion(mock_session):
    optimizer = ShoppingListOptimizer(mock_session)
    optimizer.recipes = [
        {
            "id": "r1",
            "ingredients": [
                {"item": "Flour", "quantity": 1, "unit": "kg"},
                {"item": "Oil", "quantity": 500, "unit": "ml"},
                {"item": "Salt", "quantity": 1, "unit": "tsp"}
            ]
        }
    ]

    plan_data = {"days": [{"meals": [{"id": "r1"}]}]}
    user = User(id=1, household_size=4)

    # Mock pantry: 1kg Flour, 200ml Oil
    pantry = [
        PantryItem(name="Flour", quantity=1.0, unit="kg", user_id=1),
        PantryItem(name="Oil", quantity=200.0, unit="ml", user_id=1)
    ]

    mock_session.exec.return_value.all.return_value = pantry

    # We need to mock _find_prices_for_ingredient_sync to avoid DB calls for prices
    with patch.object(optimizer, '_find_prices_for_ingredient_sync', return_value=[]):
        result = optimizer.generate_shopping_list(user, plan_data)

    # Flour should be gone (1kg - 1kg = 0)
    # Oil should be reduced (500ml - 200ml = 300ml = 0.3L)
    # Salt should remain

    # The result contains unmatched_items if no prices found
    unmatched = result["unmatched_items"]
    assert "Flour" not in unmatched
    assert "Oil" in unmatched
    assert "Salt" in unmatched

    # Check consolidated quantities before price finding if possible,
    # but the API returns the result of optimization.
    # Since we mocked prices to [], they all go to unmatched_items if they exist.
    # Let's verify Oil quantity in unmatched logic if it was priced,
    # but unmatched_items is just a list of names.

    # Better: test _subtract_pantry directly
    consolidated = {
        ("Flour", "kg"): {"qty": 1.0, "unit": "kg"},
        ("Oil", "L"): {"qty": 0.5, "unit": "L"},
        ("Salt", "tsp"): {"qty": 1.0, "unit": "tsp"}
    }
    optimizer._subtract_pantry(consolidated, pantry)

    assert ("Flour", "kg") not in consolidated
    assert consolidated[("Oil", "L")]["qty"] == 0.3
    assert consolidated[("Salt", "tsp")]["qty"] == 1.0
