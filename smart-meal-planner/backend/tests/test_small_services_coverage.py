"""Coverage for the small services: recipe, geospatial, edamam, fatsecret,
scraper_bridge and user services. Pure functions and faked sessions/HTTP.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.edamam_service import EdamamService
from app.services.fatsecret_service import FatSecretService
from app.services.geospatial_service import GeospatialService
from app.services.recipe_service import RecipeService
from app.services.scraper_bridge_service import ScraperBridgeService
from app.services.user_service import UserService


# ---------------------------------------------------------------------------
# RecipeService
# ---------------------------------------------------------------------------

class _Recipe:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def dict(self):
        return {"id": self.id, "name": self.name}


class _FakeScalars:
    def __init__(self, items):
        self._items = items

    def unique(self):
        return self

    def all(self):
        return self._items


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _FakeScalars(self._items)


@pytest.mark.asyncio
async def test_get_all_recipes_as_dicts():
    recipe = _Recipe(
        id=1, name="Soup",
        ingredients=[SimpleNamespace(name="Carrot"), SimpleNamespace(name="Onion")],
        ratings=[SimpleNamespace(rating=4), SimpleNamespace(rating=5)],
        dietary_tags_json='["vegan"]',
    )
    bad_json = _Recipe(
        id=2, name="Stew",
        ingredients=[], ratings=[],
        dietary_tags_json="{not json",
    )
    no_tags = _Recipe(
        id=3, name="Salad",
        ingredients=[], ratings=[],
        dietary_tags_json=None,
    )
    session = MagicMock()
    session.execute = AsyncMock(return_value=_FakeResult([recipe, bad_json, no_tags]))
    rows = await RecipeService(session).get_all_recipes_as_dicts()
    assert [r["name"] for r in rows] == ["Soup", "Stew", "Salad"]
    assert rows[0]["ingredients"] == ["Carrot", "Onion"]
    assert rows[0]["dietary_tags"] == ["vegan"]
    assert rows[0]["average_rating"] == 4.5
    assert rows[1]["dietary_tags"] == []
    assert rows[1]["average_rating"] == 0
    assert rows[2]["dietary_tags"] == []


def test_filter_recipes():
    recipes = [
        {"name": "A", "dietary_tags": ["Vegan", "Gluten-Free"], "allergens": ["peanuts"]},
        {"name": "B", "dietary_tags": ["vegan"], "allergens": []},
        {"name": "C", "dietary_tags": [], "allergens": ["Dairy"]},
    ]
    # No filters -> everything.
    assert RecipeService.filter_recipes(recipes, [], []) == recipes
    # Dietary preference must match all prefs (case/underscore-insensitive).
    assert [r["name"] for r in RecipeService.filter_recipes(recipes, ["gluten_free"], [])] == ["A"]
    # Allergies exclude.
    assert [r["name"] for r in RecipeService.filter_recipes(recipes, [], ["peanuts"])] == ["B", "C"]
    # Combined.
    assert [r["name"] for r in RecipeService.filter_recipes(recipes, ["vegan"], ["peanuts"])] == ["B"]
    # Missing keys default to empty lists.
    assert RecipeService.filter_recipes([{"name": "D"}], ["vegan"], []) == []


def test_scale_ingredients():
    ings = [{"name": "Flour", "quantity": 100}, {"name": "Salt"}, {"name": "Sugar", "quantity": "lots"}]
    assert RecipeService.scale_ingredients(ings, 2, 2) is ings
    assert RecipeService.scale_ingredients(ings, 0, 4) is ings
    assert RecipeService.scale_ingredients(ings, 2, 0) is ings
    scaled = RecipeService.scale_ingredients(ings, 2, 6)
    assert scaled[0]["quantity"] == 300
    assert "quantity" not in scaled[1]
    assert scaled[2]["quantity"] == "lots"  # non-numeric untouched


# ---------------------------------------------------------------------------
# GeospatialService
# ---------------------------------------------------------------------------

def test_get_coordinates():
    assert GeospatialService.get_coordinates("") is None
    assert GeospatialService.get_coordinates(None) is None
    assert GeospatialService.get_coordinates("H2X 1Y2") == (45.51, -73.57)
    assert GeospatialService.get_coordinates("h2x1y2") == (45.51, -73.57)
    assert GeospatialService.get_coordinates("Z9Z9Z9") is None


def test_calculate_distance():
    assert GeospatialService.calculate_distance(45.5, -73.57, 45.5, -73.57) == 0.0
    d = GeospatialService.calculate_distance(45.51, -73.57, 45.4954, -73.6798)
    assert 8.0 < d < 9.5  # H2X -> H4T is roughly 8.7 km


def test_get_distance_between_postal_codes():
    assert GeospatialService.get_distance_between_postal_codes("H2X1Y2", "H4T1V6") is not None
    assert GeospatialService.get_distance_between_postal_codes("H2X1Y2", "Z9Z9Z9") is None
    assert GeospatialService.get_distance_between_postal_codes("Z9Z9Z9", "H4T1V6") is None


def test_calculate_trip_travel_penalty():
    assert GeospatialService.calculate_trip_travel_penalty([]) == 0.0
    assert GeospatialService.calculate_trip_travel_penalty(["H2X1Y2"]) == 0.0
    # Two stops, no user location: one fixed stop cost.
    assert GeospatialService.calculate_trip_travel_penalty(["H2X1Y2", "H4T1V6"]) == 3.5
    # With a user location the distance legs are added (and the return leg).
    penalty = GeospatialService.calculate_trip_travel_penalty(
        ["H2X1Y2", "H4T1V6"], user_postal_code="H2X1Y2"
    )
    assert penalty > 3.5
    # Unknown postal codes contribute no distance, only the fixed cost.
    assert GeospatialService.calculate_trip_travel_penalty(
        ["Z9Z9Z9", "Y8Y8Y8"], user_postal_code="H2X1Y2"
    ) == 3.5


# ---------------------------------------------------------------------------
# EdamamService / FatSecretService (faked httpx)
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, status_code=200, payload=None, raise_error=None):
        self.status_code = status_code
        self._payload = payload or {}
        self._raise_error = raise_error

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self._raise_error is not None:
            raise self._raise_error


class _FakeHTTPClient:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, *args, **kwargs):
        if self._exc is not None:
            raise self._exc
        return self._response

    async def get(self, *args, **kwargs):
        if self._exc is not None:
            raise self._exc
        return self._response


@pytest.mark.asyncio
async def test_edamam_no_credentials():
    assert await EdamamService("", "").get_nutrition_data("Soup", ["1 carrot"]) == {}
    assert await EdamamService("id", "").get_nutrition_data("Soup", ["1 carrot"]) == {}


@pytest.mark.asyncio
async def test_edamam_success_and_parse():
    payload = {
        "calories": 250,
        "totalNutrients": {
            "PROCNT": {"quantity": 10.5},
            "CHOCDF": {"quantity": 30.2},
            "FAT": {"quantity": 5.9},
            "FIBTG": {"quantity": 2.4},
        },
    }
    client = _FakeHTTPClient(response=_FakeResponse(200, payload))
    with patch("app.services.edamam_service.httpx.AsyncClient", return_value=client):
        data = await EdamamService("id", "key").get_nutrition_data("Soup", ["1 carrot"])
    assert data == {"calories": 250, "protein": 10, "carbs": 30, "fat": 5, "fiber": 2}
    # _parse_response with missing keys defaults to zero.
    assert EdamamService("id", "key")._parse_response({}) == {
        "calories": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0,
    }


@pytest.mark.asyncio
async def test_edamam_non_200_and_exception():
    for client in (
        _FakeHTTPClient(response=_FakeResponse(401, {})),
        _FakeHTTPClient(exc=RuntimeError("boom")),
    ):
        with patch("app.services.edamam_service.httpx.AsyncClient", return_value=client):
            assert await EdamamService("id", "key").get_nutrition_data("Soup", []) == {}


@pytest.mark.asyncio
async def test_fatsecret_search_and_details():
    client = _FakeHTTPClient(response=_FakeResponse(200, {"foods": {"food": []}}))
    with patch("app.services.fatsecret_service.httpx.AsyncClient", return_value=client):
        svc = FatSecretService("key", "secret")
        assert await svc.search_food("apple") == {"foods": {"food": []}}
        assert await svc.get_food_details(123) == {"foods": {"food": []}}


@pytest.mark.asyncio
async def test_fatsecret_http_error_propagates():
    client = _FakeHTTPClient(response=_FakeResponse(200, {}, raise_error=ValueError("bad status")))
    with patch("app.services.fatsecret_service.httpx.AsyncClient", return_value=client):
        with pytest.raises(ValueError):
            await FatSecretService("key", "secret").search_food("apple")


# ---------------------------------------------------------------------------
# ScraperBridgeService
# ---------------------------------------------------------------------------

class _FakeScraper:
    def __init__(self, postal_code, headless=True):
        self.postal_code = postal_code

    async def scrape(self, limit=50):
        deal = SimpleNamespace(
            name="Apples", price=1.99, original_price=2.99, unit="lb",
            category="Produce", store="Metro",
            valid_from=None, valid_until=None,
            loyalty_program=None, loyalty_points=None,
            image_url=None, sale_info="2 for 1",
        )
        return ([{"name": "dict deal", "price": 3.0}, deal], None, None, None)


class _FailingScraper:
    def __init__(self, postal_code, headless=True):
        pass

    async def scrape(self, limit=50):
        raise RuntimeError("scraper exploded")


@pytest.mark.asyncio
async def test_scraper_bridge_unknown_store():
    assert await ScraperBridgeService.run_root_scraper("no-such-store") == []


@pytest.mark.asyncio
async def test_scraper_bridge_maps_deals():
    with patch.dict(ScraperBridgeService.SCRAPER_MAP, {"fake": _FakeScraper}):
        deals = await ScraperBridgeService.run_root_scraper("FAKE")
    assert deals[0] == {"name": "dict deal", "price": 3.0}
    assert deals[1]["name"] == "Apples"
    assert deals[1]["price"] == 1.99
    assert deals[1]["original_price"] == 2.99
    assert deals[1]["sale_info"] == "2 for 1"


@pytest.mark.asyncio
async def test_scraper_bridge_failure_returns_empty():
    with patch.dict(ScraperBridgeService.SCRAPER_MAP, {"fake": _FailingScraper}):
        assert await ScraperBridgeService.run_root_scraper("fake") == []


def test_scraper_bridge_map_deal_defaults():
    bare = SimpleNamespace(name="X")
    mapped = ScraperBridgeService._map_deal_to_dict(bare)
    assert mapped["price"] == 0.0
    assert mapped["original_price"] == 0.0  # falls back to price
    assert mapped["unit"] == "each"
    assert mapped["category"] == "Grocery"
    assert mapped["store"] == ""


# ---------------------------------------------------------------------------
# UserService
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_service_get_user():
    session = MagicMock()
    session.get = AsyncMock(return_value=SimpleNamespace(id=1, name="Ann"))
    assert (await UserService(session).get_user(1)).name == "Ann"
    session.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_user_service_update_user_not_found():
    session = MagicMock()
    session.get = AsyncMock(return_value=None)
    assert await UserService(session).update_user(99, MagicMock()) is None


@pytest.mark.asyncio
async def test_user_service_update_user():
    from app.schemas import UserUpdate

    user = SimpleNamespace(
        id=1, allergies=["peanuts"], preferred_loyalty_programs=["PC Optimum"],
        household_size=2, name="Ann",
    )
    session = MagicMock()
    session.get = AsyncMock(return_value=user)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    updated = await UserService(session).update_user(
        1, UserUpdate(household_size=4, allergies=["dairy"], preferred_loyalty_programs=["Moi"])
    )
    assert updated.household_size == 4
    assert updated.allergies == ["dairy"]
    assert updated.preferred_loyalty_programs == ["Moi"]
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_user_service_nutrition_summary_no_user_or_plan():
    session = MagicMock()
    session.get = AsyncMock(return_value=None)
    assert await UserService(session).get_meal_plan_nutrition_summary(99) == {}

    session.get = AsyncMock(return_value=SimpleNamespace(id=1))

    class _FirstResult:
        def scalars(self):
            return self

        def first(self):
            return None

    session.execute = AsyncMock(return_value=_FirstResult())
    assert await UserService(session).get_meal_plan_nutrition_summary(1) == {}


@pytest.mark.asyncio
async def test_user_service_nutrition_summary():
    plan_data = {
        "meal_plan": [
            {"meals": [
                {"recipe_id": 7, "nutrition": {"calories": 999}},  # recipe wins
                {"nutrition": {"calories": 100, "protein": 5, "fat": 2, "carbs": 10, "fiber": 1}},
                {"nutrition": {"calories": "bad", "fats": 3}},  # 'fats' key + bad value
            ]},
            {"meals": [{"recipe_id": 8}]},  # unknown recipe id -> meal nutrition (none)
        ]
    }
    plan = SimpleNamespace(content_json=json.dumps(plan_data))
    recipe = SimpleNamespace(id=7, nutrition_json=json.dumps(
        {"calories": 400, "protein": 20, "carbs": 30, "fat": 10, "fiber": 5}
    ))

    class _PlanResult:
        def scalars(self):
            return self

        def first(self):
            return plan

    class _RecipeResult:
        def scalars(self):
            return self

        def all(self):
            return [recipe]

    session = MagicMock()
    session.get = AsyncMock(return_value=SimpleNamespace(id=1))
    session.execute = AsyncMock(side_effect=[_PlanResult(), _RecipeResult()])
    summary = await UserService(session).get_meal_plan_nutrition_summary(1)
    # totals: recipe 400/20/30/10/5 + meal 100/5/10/2/1 + meal 0/0/0/3/0
    assert summary["totals"] == {
        "calories": 500.0, "protein": 25.0, "carbs": 40.0, "fat": 15.0, "fiber": 6.0,
    }
    assert summary["daily_averages"] == {
        "calories": 250.0, "protein": 12.5, "carbs": 20.0, "fat": 7.5, "fiber": 3.0,
    }
