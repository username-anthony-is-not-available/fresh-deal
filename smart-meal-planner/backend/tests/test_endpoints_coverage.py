"""Coverage tests for app/api/endpoints.py via the TestClient."""
import json
import os
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import create_access_token
from app.main import app
from app.models.all_models import (
    Deal,
    Feedback,
    MealPlan,
    PantryItem,
    Product,
    Recipe,
    RecipeRating,
    ScraperLog,
    Store,
    User,
    UserFavorite,
)
from app.services.deal_cache_service import deal_cache


@pytest_asyncio.fixture(name="test_user")
async def user_fixture(session: AsyncSession):
    user = User(
        email="ep@test.com",
        hashed_password="hashed",
        postal_code="H4T1V6",
        household_size=2,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest_asyncio.fixture(name="test_recipe")
async def recipe_fixture(session: AsyncSession):
    recipe = Recipe(
        name="Chicken Pasta",
        cuisine="Italian",
        prep_time_minutes=20,
        servings=4,
        ingredients_json=json.dumps(
            [{"item": "Chicken", "quantity": 1, "unit": "kg"}]
        ),
        instructions_json=json.dumps(["Boil pasta."]),
    )
    session.add(recipe)
    await session.commit()
    await session.refresh(recipe)
    return recipe


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


async def _add_store_product_deal(session, price=5.0, original=10.0):
    store = Store(name="Metro", chain="Metro", postal_code="H3Z1T5")
    product = Product(name="Chicken Breast", category="Meat", unit_type="kg")
    session.add(store)
    session.add(product)
    await session.commit()
    await session.refresh(store)
    await session.refresh(product)
    deal = Deal(
        product_id=product.id,
        store_id=store.id,
        price=price,
        original_price=original,
        discount_pct=50.0,
        valid_from=date.today(),
        valid_until=date.today() + timedelta(days=7),
    )
    session.add(deal)
    await session.commit()
    await session.refresh(deal)
    return store, product, deal


# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_recipes_filters(client: AsyncClient, session: AsyncSession, test_recipe):
    other = Recipe(
        name="Beef Tacos",
        cuisine="Mexican",
        prep_time_minutes=45,
        servings=2,
        ingredients_json=json.dumps([{"item": "Beef", "quantity": 1, "unit": "kg"}]),
        instructions_json="[]",
    )
    session.add(other)
    await session.commit()
    await session.refresh(other)
    # The search path inner-joins RecipeIngredient, so rows must exist.
    from app.models.all_models import RecipeIngredient

    session.add(RecipeIngredient(recipe_id=test_recipe.id, name="chicken", original_text="Chicken"))
    session.add(RecipeIngredient(recipe_id=other.id, name="beef", original_text="Beef"))
    await session.commit()

    resp = await client.get("/api/recipes")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp = await client.get("/api/recipes", params={"search": "chicken"})
    assert [r["name"] for r in resp.json()] == ["Chicken Pasta"]

    resp = await client.get("/api/recipes", params={"search": "beef"})
    assert [r["name"] for r in resp.json()] == ["Beef Tacos"]

    resp = await client.get("/api/recipes", params={"cuisine": "italian"})
    assert [r["name"] for r in resp.json()] == ["Chicken Pasta"]

    resp = await client.get("/api/recipes", params={"prep_time": 30})
    assert [r["name"] for r in resp.json()] == ["Chicken Pasta"]


@pytest.mark.asyncio
async def test_get_recipe_variants(client: AsyncClient, session: AsyncSession, test_user, test_recipe):
    headers = _headers(test_user)
    # Explicit servings.
    resp = await client.get(
        f"/api/recipes/{test_recipe.id}", params={"servings": 2}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["servings"] == 2

    # Authenticated: servings default to the user's household size.
    resp = await client.get(
        f"/api/recipes/{test_recipe.id}", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["servings"] == 2

    # Valid token for an unknown user: optional auth resolves to no user,
    # so servings default to the recipe's own serving size.
    ghost = {"Authorization": f"Bearer {create_access_token('99999')}"}
    resp = await client.get(f"/api/recipes/{test_recipe.id}", headers=ghost)
    assert resp.status_code == 200
    assert resp.json()["servings"] == 4

    # Not found (auth header required: the OAuth2 scheme 401s without one).
    resp = await client.get("/api/recipes/99999", headers=headers)
    assert resp.status_code == 404

    # Unparseable ingredients JSON falls back to an empty list.
    broken = Recipe(
        name="Broken", servings=4, ingredients_json="not json", instructions_json="[]"
    )
    session.add(broken)
    await session.commit()
    await session.refresh(broken)
    resp = await client.get(f"/api/recipes/{broken.id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["ingredients"] == []

    # Plain-string ingredients fall back to name-only substitution lookup.
    # (Only reachable when target == base servings: scale_ingredients
    # crashes on string ingredients otherwise -- observed behaviour.)
    strings = Recipe(
        name="Strings",
        servings=4,
        ingredients_json=json.dumps(["salt", "pepper"]),
        instructions_json="[]",
    )
    session.add(strings)
    await session.commit()
    await session.refresh(strings)
    resp = await client.get(
        f"/api/recipes/{strings.id}", params={"servings": 4}, headers=headers
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_top_rated_recipes(client: AsyncClient, session: AsyncSession, test_user, test_recipe):
    # OBSERVED BUG (not fixed here): GET /api/recipes/top-rated is
    # unreachable via HTTP -- Starlette matches /recipes/{recipe_id} first
    # and the int validation fails (401 without auth, 422 with auth) instead
    # of falling through. Exercise the handler directly.
    from app.api.endpoints import get_top_rated_recipes

    other = Recipe(name="Salad", servings=2, ingredients_json="[]", instructions_json="[]")
    session.add(other)
    await session.commit()
    await session.refresh(other)
    session.add(RecipeRating(user_id=test_user.id, recipe_id=other.id, rating=3))
    session.add(RecipeRating(user_id=test_user.id, recipe_id=test_recipe.id, rating=5))
    await session.commit()
    result = await get_top_rated_recipes(limit=5, session=session)
    assert [r.name for r in result][0] == "Chicken Pasta"
    assert result[0].average_rating == 5


@pytest.mark.asyncio
async def test_rate_recipe_updates_existing(client: AsyncClient, test_user, test_recipe):
    headers = _headers(test_user)
    resp = await client.post(
        f"/api/recipes/{test_recipe.id}/rate", json={"rating": 5}, headers=headers
    )
    assert resp.status_code == 200
    resp = await client.post(
        f"/api/recipes/{test_recipe.id}/rate", json={"rating": 3}, headers=headers
    )
    assert resp.status_code == 200
    resp = await client.get(f"/api/recipes/{test_recipe.id}/my-rating", headers=headers)
    assert resp.json() == {"rating": 3}


@pytest.mark.asyncio
async def test_my_rating_and_average_without_ratings(client: AsyncClient, test_user, test_recipe):
    headers = _headers(test_user)
    resp = await client.get(f"/api/recipes/{test_recipe.id}/my-rating", headers=headers)
    assert resp.json() == {"rating": None}
    resp = await client.get(f"/api/recipes/{test_recipe.id}/average-rating")
    assert resp.json() == {"average_rating": 0}


@pytest.mark.asyncio
async def test_favorites_round_trip(client: AsyncClient, test_user, test_recipe):
    headers = _headers(test_user)
    # Unfavorite when nothing is favorited -> 404.
    resp = await client.delete(f"/api/recipes/{test_recipe.id}/favorite", headers=headers)
    assert resp.status_code == 404
    resp = await client.get("/api/users/me/favorites", headers=headers)
    assert resp.json() == []
    resp = await client.post(f"/api/recipes/{test_recipe.id}/favorite", headers=headers)
    assert resp.status_code == 200
    resp = await client.get("/api/users/me/favorites", headers=headers)
    assert len(resp.json()) == 1
    resp = await client.delete(f"/api/recipes/{test_recipe.id}/favorite", headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_update_user_not_found(client: AsyncClient):
    assert (await client.get("/api/users/99999")).status_code == 404
    assert (
        await client.patch("/api/users/99999", json={"postal_code": "H1A1A1"})
    ).status_code == 404


@pytest.mark.asyncio
async def test_nutrition_summary_not_found(client: AsyncClient, test_user):
    resp = await client.get(f"/api/users/{test_user.id}/nutrition-summary")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_nutrition_summary_happy_path(client: AsyncClient, session: AsyncSession, test_user, test_recipe):
    session.add(
        MealPlan(
            user_id=test_user.id,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=6),
            content_json=json.dumps(
                {"days": [{"meals": [{"recipe_id": test_recipe.id}]}]}
            ),
        )
    )
    await session.commit()
    resp = await client.get(f"/api/users/{test_user.id}/nutrition-summary")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Seed + scrape triggers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seed_data(client: AsyncClient, session: AsyncSession):
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session as SyncSession, create_engine
    from sqlmodel import SQLModel

    # StaticPool: FastAPI runs sync dependencies in a threadpool, so the
    # in-memory DB must live on one shared connection.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    sync_session = SyncSession(engine)

    def _override():
        yield sync_session

    app.dependency_overrides[get_session] = _override
    try:
        resp = await client.post("/api/data/seed")
    finally:
        app.dependency_overrides.pop(get_session, None)
    assert resp.status_code == 200
    assert "Seeded database with 50 deals." in resp.json()["message"]


@pytest.mark.asyncio
async def test_trigger_scrape_variants(client: AsyncClient, test_user, monkeypatch):
    fake_task = SimpleNamespace(id="task-123")
    fake_scrape = SimpleNamespace(delay=MagicMock(return_value=fake_task))
    monkeypatch.setattr("app.api.endpoints.scrape_task", fake_scrape)
    headers = _headers(test_user)

    resp = await client.post(
        "/api/admin/scrape",
        json={"stores": ["metro"], "postal_code": "H4T1V6", "limit": 10},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["task_id"] == "task-123"
    assert resp.json()["stores"] == ["metro"]

    # Defaults: all stores, limit 50.
    resp = await client.post("/api/admin/scrape", json={}, headers=headers)
    assert resp.json()["stores"] == ["metro", "walmart", "maxi", "iga", "provigo", "super_c"]

    # limit_per_store fallback.
    resp = await client.post(
        "/api/admin/scrape", json={"limit_per_store": 7}, headers=headers
    )
    assert resp.status_code == 200

    resp = await client.post(
        "/api/admin/scrape/flipp", json={"stores": ["iga"]}, headers=headers
    )
    assert resp.status_code == 200
    assert fake_scrape.delay.call_args.kwargs["scraper_type"] == "flipp"

    resp = await client.post(
        "/api/admin/scrape/metro",
        params={"postal_code": "H4T1V6", "limit": 5},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["stores"] == ["metro"]


@pytest.mark.asyncio
async def test_trigger_local_scrape_now(client: AsyncClient, test_user, monkeypatch):
    fake_task = SimpleNamespace(id="task-9")
    fake_scrape = SimpleNamespace(delay=MagicMock(return_value=fake_task))
    monkeypatch.setattr("app.api.endpoints.scrape_task", fake_scrape)

    # Explicit postal code. NOTE: the endpoint references an unimported
    # `datetime` name when building its response (NameError) -- observed
    # behaviour, not fixed here. The scrape task itself is still triggered.
    with pytest.raises(NameError):
        await client.post(
            "/api/scrape/trigger",
            params={"postal_code": "H2X1Y2"},
            headers=_headers(test_user),
        )
    assert fake_scrape.delay.called

    # Authenticated user: postal code comes from the user (same NameError).
    with pytest.raises(NameError):
        await client.post("/api/scrape/trigger", headers=_headers(test_user))

    # No header at all: the OAuth2 scheme rejects the request first.
    resp = await client.post("/api/scrape/trigger")
    assert resp.status_code == 401

    # Garbage token: optional auth resolves to no user, and the endpoint
    # references an unimported `settings` name (NameError) -- observed
    # behaviour, not fixed here.
    with pytest.raises(NameError):
        await client.post(
            "/api/scrape/trigger", headers={"Authorization": "Bearer garbage"}
        )


@pytest.mark.asyncio
async def test_get_last_scraped_info(client: AsyncClient, session: AsyncSession):
    # OBSERVED BUG (not fixed here -- coverage-only issue): Deal has no
    # `created_at` column, so this endpoint always raises AttributeError
    # while building its query. The test client re-raises server exceptions.
    with pytest.raises(AttributeError):
        await client.get("/api/scrape/last-scraped")
    await _add_store_product_deal(session)
    with pytest.raises(AttributeError):
        await client.get("/api/scrape/last-scraped")


@pytest.mark.asyncio
async def test_list_scrapers_and_status(client: AsyncClient, session: AsyncSession, test_user):
    headers = _headers(test_user)
    resp = await client.get("/api/admin/scrapers", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["scrapers"][0]["id"] == "default"
    resp = await client.get("/api/admin/status/scrapers", headers=headers)
    assert resp.json() == []
    store = Store(name="Metro", chain="Metro", postal_code="H3Z1T5")
    session.add(store)
    await session.commit()
    resp = await client.get("/api/admin/status/scrapers", headers=headers)
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "Metro"


@pytest.mark.asyncio
async def test_scraper_health_endpoints(client: AsyncClient, test_user):
    headers = _headers(test_user)
    resp = await client.get("/api/admin/scrapers/health", headers=headers)
    assert resp.status_code == 200
    resp = await client.get("/api/admin/scrapers/health/summary", headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Scraper logs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scraper_logs_filters(client: AsyncClient, session: AsyncSession, test_user):
    headers = _headers(test_user)
    session.add(ScraperLog(store_name="metro", status="success"))
    session.add(ScraperLog(store_name="iga", status="failure"))
    session.add(ScraperLog(store_name="metro", status="failure"))
    await session.commit()
    resp = await client.get("/api/admin/scrapers/logs", headers=headers)
    assert len(resp.json()) == 3
    resp = await client.get(
        "/api/admin/scrapers/logs", params={"store_name": "metro"}, headers=headers
    )
    assert len(resp.json()) == 2
    resp = await client.get(
        "/api/admin/scrapers/logs", params={"status": "failure"}, headers=headers
    )
    assert len(resp.json()) == 2
    resp = await client.get(
        "/api/admin/scrapers/logs", params={"limit": 1, "offset": 1}, headers=headers
    )
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_scraper_log_screenshot_and_html(client: AsyncClient, session: AsyncSession, test_user):
    headers = _headers(test_user)
    os.makedirs("/tmp/scrapers", exist_ok=True)
    png_path = "/tmp/scrapers/test-shot.png"
    html_path = "/tmp/scrapers/test-snap.html"
    with open(png_path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
    with open(html_path, "w") as f:
        f.write("<html><body>hi</body></html>")
    try:
        no_paths = ScraperLog(store_name="metro", status="success")
        outside = ScraperLog(
            store_name="metro", status="success", screenshot_path="/etc/passwd",
            html_path="/etc/passwd",
        )
        missing = ScraperLog(
            store_name="metro", status="success",
            screenshot_path="/tmp/scrapers/nope.png",
            html_path="/tmp/scrapers/nope.html",
        )
        good = ScraperLog(
            store_name="metro", status="success",
            screenshot_path=png_path, html_path=html_path,
        )
        session.add_all([no_paths, outside, missing, good])
        await session.commit()
        for log in (no_paths, outside, missing, good):
            await session.refresh(log)

        # No paths at all -> 404.
        assert (
            await client.get(f"/api/admin/scrapers/logs/{no_paths.id}/screenshot", headers=headers)
        ).status_code == 404
        assert (
            await client.get(f"/api/admin/scrapers/logs/{no_paths.id}/html", headers=headers)
        ).status_code == 404
        # Outside /tmp/scrapers -> 403.
        assert (
            await client.get(f"/api/admin/scrapers/logs/{outside.id}/screenshot", headers=headers)
        ).status_code == 403
        assert (
            await client.get(f"/api/admin/scrapers/logs/{outside.id}/html", headers=headers)
        ).status_code == 403
        # Inside but missing on disk -> 404.
        assert (
            await client.get(f"/api/admin/scrapers/logs/{missing.id}/screenshot", headers=headers)
        ).status_code == 404
        assert (
            await client.get(f"/api/admin/scrapers/logs/{missing.id}/html", headers=headers)
        ).status_code == 404
        # Real files -> 200.
        resp = await client.get(f"/api/admin/scrapers/logs/{good.id}/screenshot", headers=headers)
        assert resp.status_code == 200
        resp = await client.get(f"/api/admin/scrapers/logs/{good.id}/html", headers=headers)
        assert resp.status_code == 200
    finally:
        for p in (png_path, html_path):
            if os.path.exists(p):
                os.remove(p)


@pytest.mark.asyncio
async def test_reset_scraper_circuit_breaker(client: AsyncClient, test_user):
    resp = await client.post(
        "/api/admin/scrapers/metro/reset", headers=_headers(test_user)
    )
    assert resp.status_code == 200
    assert "metro" in resp.json()["message"]


# ---------------------------------------------------------------------------
# Innovative suggestions + cache
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_innovative_meal_suggestions_forbidden(client: AsyncClient, test_user):
    resp = await client.post(
        "/api/innovative-meal-suggestions",
        params={"user_id": test_user.id + 1},
        headers=_headers(test_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_innovative_meal_suggestions_errors(client: AsyncClient, test_user, monkeypatch):
    headers = _headers(test_user)

    class _FailingAI:
        def __init__(self, _session):
            pass

        async def get_innovative_meal_suggestions(self, **_kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr("app.api.endpoints.AIInnovationService", _FailingAI)
    resp = await client.post(
        "/api/innovative-meal-suggestions",
        params={"user_id": test_user.id},
        headers=headers,
    )
    assert resp.status_code == 500

    class _ValueErrorAI:
        def __init__(self, _session):
            pass

        async def get_innovative_meal_suggestions(self, **_kwargs):
            raise ValueError("No deals available")

    monkeypatch.setattr("app.api.endpoints.AIInnovationService", _ValueErrorAI)
    resp = await client.post(
        "/api/innovative-meal-suggestions",
        params={"user_id": test_user.id},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invalidate_deal_cache(client: AsyncClient, test_user):
    resp = await client.post("/api/deals/cache/invalidate", headers=_headers(test_user))
    assert resp.status_code == 200
    assert resp.json()["status"] == "invalidated"


# ---------------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_deals_variants(client: AsyncClient, session: AsyncSession, monkeypatch):
    store, product, deal = await _add_store_product_deal(session)
    # A second, cheaper deal for another category/store.
    store2 = Store(name="Walmart", chain="Walmart", postal_code="H4T1V6")
    product2 = Product(name="Milk", category="Dairy", unit_type="L")
    session.add(store2)
    session.add(product2)
    await session.commit()
    await session.refresh(store2)
    await session.refresh(product2)
    session.add(
        Deal(
            product_id=product2.id, store_id=store2.id, price=2.0,
            original_price=4.0, discount_pct=50.0,
            valid_from=date.today() - timedelta(days=1),
            valid_until=date.today() + timedelta(days=7),
            loyalty_program="PC Optimum", loyalty_points=1000,
        )
    )
    await session.commit()

    def _get(**params):
        deal_cache.invalidate_deals()
        return client.get("/api/deals", params=params)

    resp = await _get()
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp = await _get(category="dairy")
    assert [d["product"]["name"] for d in resp.json()] == ["Milk"]

    resp = await _get(store="walmart")
    assert [d["product"]["name"] for d in resp.json()] == ["Milk"]

    resp = await _get(min_discount=60)
    assert resp.json() == []

    resp = await _get(active_only=True)
    assert len(resp.json()) == 2

    resp = await _get(sort_by="category")
    assert [d["product"]["category"] for d in resp.json()] == ["Dairy", "Meat"]

    resp = await _get(sort_by="discount_pct")
    assert len(resp.json()) == 2

    resp = await _get(sort_by="effective_discount")
    # Milk: 2.00 - 1000*0.001 = 1.00 effective; Chicken: 5.00.
    assert resp.json()[0]["product"]["name"] == "Milk"

    resp = await _get(limit=1, offset=1)
    assert len(resp.json()) == 1

    # Postal-code path uses the geospatial service; stub distances.
    monkeypatch.setattr(
        "app.api.endpoints.GeospatialService.get_distance_between_postal_codes",
        staticmethod(lambda _a, _b: 2.0),
    )
    resp = await _get(postal_code="H4T1V6", sort_by="distance")
    assert len(resp.json()) == 2
    assert resp.json()[0]["distance"] == 2.0

    monkeypatch.setattr(
        "app.api.endpoints.GeospatialService.get_distance_between_postal_codes",
        staticmethod(lambda _a, _b: 10.0),
    )
    resp = await _get(postal_code="H4T1V6")
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Meal plans + tasks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_meal_plan_task(client: AsyncClient, monkeypatch):
    fake = SimpleNamespace(delay=MagicMock(return_value=SimpleNamespace(id="plan-1")))
    monkeypatch.setattr("app.api.endpoints.generate_meal_plan_task", fake)
    resp = await client.post("/api/plans/generate", params={"user_id": 1})
    assert resp.status_code == 200
    assert resp.json()["task_id"] == "plan-1"


@pytest.mark.asyncio
async def test_regenerate_meal(client: AsyncClient, session: AsyncSession, test_user, monkeypatch):
    body = {
        "user_id": test_user.id,
        "day": "Monday",
        "type": "Dinner",
        "dietary_preferences": [],
        "existing_meals": [],
    }
    # Unknown user -> 404.
    resp = await client.post(
        "/api/plans/regenerate-meal", json={**body, "user_id": 99999}
    )
    assert resp.status_code == 404

    class _FakeLLM:
        def __init__(self):
            pass

        async def regenerate_single_meal(self, **_kwargs):
            return {"name": "New Meal", "recipe_id": 1}

    monkeypatch.setattr("app.api.endpoints.LLMService", _FakeLLM)
    resp = await client.post("/api/plans/regenerate-meal", json=body)
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Meal"

    class _NoneLLM:
        def __init__(self):
            pass

        async def regenerate_single_meal(self, **_kwargs):
            return None

    monkeypatch.setattr("app.api.endpoints.LLMService", _NoneLLM)
    resp = await client.post("/api/plans/regenerate-meal", json=body)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_task_status_states(client: AsyncClient, monkeypatch):
    def _fake_result(state, result=None, info=None):
        class _R:
            def __init__(self, _task_id):
                self.state = state
                self.result = result
                self.info = info
        return _R

    for state, expected in [
        ("PENDING", "Pending"),
        ("REVOKED", "Stopped"),
        ("SUCCESS", "SUCCESS"),
    ]:
        monkeypatch.setattr(
            "app.api.endpoints.AsyncResult", _fake_result(state, result={"x": 1})
        )
        resp = await client.get("/api/tasks/abc")
        assert resp.status_code == 200
        assert resp.json()["status"] == expected

    monkeypatch.setattr(
        "app.api.endpoints.AsyncResult", _fake_result("FAILURE", info="kaboom")
    )
    resp = await client.get("/api/tasks/abc")
    assert resp.json() == {"task_id": "abc", "status": "Failed", "error": "kaboom"}


@pytest.mark.asyncio
async def test_stop_task(client: AsyncClient, monkeypatch):
    revoke = MagicMock()
    fake_app = SimpleNamespace(control=SimpleNamespace(revoke=revoke))
    # NB: `import app.celery_app as X` binds the Celery instance, not the
    # module (the package attribute was overwritten); go via importlib.
    import importlib

    celery_app_module = importlib.import_module("app.celery_app")
    monkeypatch.setattr(celery_app_module, "celery_app", fake_app)
    resp = await client.post("/api/tasks/abc/stop")
    assert resp.status_code == 200
    assert resp.json()["status"] == "Stopped"
    revoke.assert_called_once_with("abc", terminate=True, signal="SIGTERM")


@pytest.mark.asyncio
async def test_get_latest_plan(client: AsyncClient, session: AsyncSession, test_user):
    resp = await client.get(f"/api/plans/{test_user.id}/latest")
    assert resp.status_code == 404
    plan = MealPlan(
        user_id=test_user.id,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=6),
        content_json=json.dumps({"days": [{"meals": []}]}),
    )
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    resp = await client.get(f"/api/plans/{test_user.id}/latest")
    assert resp.status_code == 200
    assert resp.json()["id"] == plan.id
    # Empty content -> 404.
    plan.content_json = ""
    session.add(plan)
    await session.commit()
    resp = await client.get(f"/api/plans/{test_user.id}/latest")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_optimize_shopping_list(client: AsyncClient, session: AsyncSession, test_user):
    resp = await client.get("/api/shopping/optimize", params={"user_id": 99999})
    assert resp.status_code == 404
    resp = await client.get("/api/shopping/optimize", params={"user_id": test_user.id})
    assert resp.status_code == 404  # no plan yet
    plan = MealPlan(
        user_id=test_user.id,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=6),
        content_json=json.dumps(
            {"days": [{"meals": [{"ingredients": [{"item": "Chicken Breast", "quantity": 1, "unit": "kg"}]}]}]}
        ),
    )
    session.add(plan)
    await session.commit()
    await _add_store_product_deal(session)
    resp = await client.get(
        "/api/shopping/optimize",
        params={"user_id": test_user.id, "strategy": "min_cost"},
    )
    assert resp.status_code == 200
    resp = await client.get(
        "/api/shopping/optimize",
        params={
            "user_id": test_user.id,
            "strategy": "single_store",
            "preferred_stores": ["Metro"],
        },
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Pantry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pantry_round_trip(client: AsyncClient, test_user):
    uid = test_user.id
    resp = await client.get(f"/api/pantry/{uid}")
    assert resp.json() == []
    resp = await client.post(
        f"/api/pantry/{uid}/add",
        json={"items": [{"name": "Rice", "quantity": 1, "unit": "kg"}]},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    item_id = resp.json()[0]["id"]
    resp = await client.get(f"/api/pantry/{uid}")
    assert len(resp.json()) == 1
    # Wrong user -> 404.
    resp = await client.delete(f"/api/pantry/{uid + 1}/{item_id}")
    assert resp.status_code == 404
    resp = await client.delete(f"/api/pantry/{uid}/99999")
    assert resp.status_code == 404
    resp = await client.delete(f"/api/pantry/{uid}/{item_id}")
    assert resp.status_code == 200
    assert resp.json() == {"message": "Pantry item deleted"}


@pytest.mark.asyncio
async def test_consume_pantry_from_latest_plan(client: AsyncClient, session: AsyncSession, test_user):
    resp = await client.post(f"/api/pantry/99999/consume-latest-plan")
    assert resp.status_code == 404
    session.add(
        MealPlan(
            user_id=test_user.id,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=6),
            content_json=json.dumps(
                {"days": [{"meals": [{"ingredients": [{"item": "Rice", "quantity": 1, "unit": "kg"}]}]}]}
            ),
        )
    )
    session.add(PantryItem(user_id=test_user.id, name="Rice", quantity=1, unit="kg"))
    await session.commit()
    resp = await client.post(f"/api/pantry/{test_user.id}/consume-latest-plan")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_feedback_filters(client: AsyncClient, session: AsyncSession, test_user):
    headers = _headers(test_user)
    session.add_all([
        Feedback(user_id=test_user.id, recipe_id=1, rating=5, comment="great"),
        Feedback(user_id=test_user.id, meal_plan_id=1, rating=3),
        Feedback(user_id=test_user.id, recipe_id=2, rating=4),
    ])
    await session.commit()
    resp = await client.get("/api/feedback", headers=headers)
    assert len(resp.json()) == 3
    resp = await client.get("/api/feedback", params={"recipe_id": 1}, headers=headers)
    assert len(resp.json()) == 1
    resp = await client.get("/api/feedback", params={"meal_plan_id": 1}, headers=headers)
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_feedback_summary_empty_and_filled(client: AsyncClient, session: AsyncSession, test_user):
    headers = _headers(test_user)
    resp = await client.get("/api/feedback/summary", headers=headers)
    assert resp.json() == {
        "average_recipe_rating": 0,
        "average_meal_plan_rating": 0,
        "total_feedback_count": 0,
    }
    session.add_all([
        Feedback(user_id=test_user.id, recipe_id=1, rating=5),
        Feedback(user_id=test_user.id, meal_plan_id=1, rating=3),
    ])
    await session.commit()
    resp = await client.get("/api/feedback/summary", headers=headers)
    assert resp.json()["average_recipe_rating"] == 5.0
    assert resp.json()["average_meal_plan_rating"] == 3.0
    assert resp.json()["total_feedback_count"] == 2
