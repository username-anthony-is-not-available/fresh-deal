
import pytest
from unittest.mock import MagicMock
from app.services.shopping_optimizer import ShoppingListOptimizer
from app.models.all_models import User

@pytest.fixture
def mock_session():
    return MagicMock()

def test_trip_efficiency_calculation(mock_session):
    optimizer = ShoppingListOptimizer(mock_session)

    # 3 items requested
    priced_items = [
        {
            "ingredient": "Milk", "quantity": 1, "unit": "L",
            "options": [{"store_name": "Store A", "store_id": 1, "chain": "C1", "price": 2.0, "category": "Dairy"}]
        },
        {
            "ingredient": "Bread", "quantity": 1, "unit": "Loaf",
            "options": [{"store_name": "Store A", "store_id": 1, "chain": "C1", "price": 3.0, "category": "Bakery"}]
        },
        {
            "ingredient": "Eggs", "quantity": 1, "unit": "doz",
            "options": [{"store_name": "Store B", "store_id": 2, "chain": "C2", "price": 4.0, "category": "Dairy"}]
        }
    ]

    result = optimizer._optimize_routes(priced_items, strategy="min_cost")

    # Store A has 2/3 items = 66.7%
    # Store B has 1/3 items = 33.3%
    comp = result["single_store_comparison"]
    store_a = next(s for s in comp if s["name"] == "Store A")
    store_b = next(s for s in comp if s["name"] == "Store B")

    assert store_a["trip_efficiency"] == 66.7
    assert store_b["trip_efficiency"] == 33.3
    assert result["total_items_count"] == 3
    # Overall efficiency (all items found) = 100%
    assert result["trip_efficiency"] == 100.0

def test_preferred_stores_influence(mock_session):
    optimizer = ShoppingListOptimizer(mock_session)

    # Item available at both Store A and Store B
    # Store A is slightly more expensive
    priced_items = [
        {
            "ingredient": "Milk", "quantity": 1, "unit": "L",
            "options": [
                {"store_name": "Store A", "store_id": 1, "chain": "C1", "price": 2.5, "category": "Dairy"},
                {"store_name": "Store B", "store_id": 2, "chain": "C2", "price": 2.0, "category": "Dairy"}
            ]
        }
    ]

    # Without preference, min_cost/convenience should pick Store B (cheaper)
    res1 = optimizer._optimize_routes(priced_items, strategy="convenience")
    assert res1["recommended_stores"][0]["store"] == "Store B"

    # With Store A preferred, it should pick Store A despite being more expensive
    res2 = optimizer._optimize_routes(priced_items, strategy="convenience", preferred_stores=["Store A"])
    assert res2["recommended_stores"][0]["store"] == "Store A"

def test_unmatched_items_efficiency(mock_session):
    optimizer = ShoppingListOptimizer(mock_session)

    # 2 items, 1 unmatched
    priced_items = [
        {
            "ingredient": "Milk", "quantity": 1, "unit": "L",
            "options": [{"store_name": "Store A", "store_id": 1, "chain": "C1", "price": 2.0, "category": "Dairy"}]
        },
        {
            "ingredient": "Rare Spice", "quantity": 1, "unit": "g",
            "options": [] # Not found
        }
    ]

    result = optimizer._optimize_routes(priced_items, strategy="min_cost")

    # 1/2 items found = 50%
    assert result["trip_efficiency"] == 50.0
    assert "Rare Spice" in result["unmatched_items"]
