"""Coverage for app/tasks.py (Celery tasks).

Tasks are called directly (synchronously, no broker); the database sessions,
agents and Celery group dispatch are faked.
"""

import asyncio
import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.tasks as tasks
from app.tasks import (
    _get_or_create_event_loop,
    cleanup_old_data_task,
    generate_meal_plan_task,
    scrape_store_task,
    scrape_task,
    send_daily_digests_task,
    send_user_digest_email_task,
    sync_root_scrapers_task,
)


class _FakeAsyncSession:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return False


class _FakeSessionCM:
    """Sync session context manager yielding a fake session."""

    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, *args):
        return False


def _fake_group(*args, **kwargs):
    return SimpleNamespace(apply_async=lambda: SimpleNamespace(id="group-1"))


# ---------------------------------------------------------------------------
# _get_or_create_event_loop
# ---------------------------------------------------------------------------

def test_get_or_create_event_loop_reuses_open_loop():
    loop = _get_or_create_event_loop()
    assert loop is _get_or_create_event_loop()
    assert not loop.is_closed()


def test_get_or_create_event_loop_replaces_closed_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.close()
    new_loop = _get_or_create_event_loop()
    assert new_loop is not loop
    assert not new_loop.is_closed()
    new_loop.close()
    asyncio.set_event_loop(None)


# ---------------------------------------------------------------------------
# scrape_store_task / scrape_task / sync_root_scrapers_task
# ---------------------------------------------------------------------------

class _FakeScraperAgent:
    def __init__(self, session, postal_code):
        self.session = session
        self.postal_code = postal_code

    async def scrape_and_persist_single_store(self, store_name, limit=None, scraper_type=None):
        return {"store": store_name, "deals": 3}


class _FailingScraperAgent(_FakeScraperAgent):
    async def scrape_and_persist_single_store(self, *args, **kwargs):
        raise RuntimeError("scraper exploded")


def test_scrape_store_task_success():
    session = MagicMock()
    with patch.object(tasks, "AsyncSession",
                      lambda *a, **k: _FakeAsyncSession(session)), \
         patch.object(tasks, "ScraperAgent", _FakeScraperAgent):
        result = scrape_store_task("metro", postal_code="H2X1Y2", limit_per_store=10)
    assert result == {"store": "metro", "deals": 3}


def test_scrape_store_task_failure():
    session = MagicMock()
    with patch.object(tasks, "AsyncSession",
                      lambda *a, **k: _FakeAsyncSession(session)), \
         patch.object(tasks, "ScraperAgent", _FailingScraperAgent):
        result = scrape_store_task("metro")
    assert result["store"] == "metro"
    assert "scraper exploded" in result["error"]


def test_scrape_task_default_and_explicit_stores():
    with patch.object(tasks, "group", _fake_group):
        result = scrape_task()
    assert result["status"] == "Dispatched"
    assert result["group_id"] == "group-1"
    assert result["stores"]
    with patch.object(tasks, "group", _fake_group):
        result = scrape_task(stores=["metro"], postal_code="H2X1Y2")
    assert result["stores"] == ["metro"]


def test_sync_root_scrapers_task():
    with patch.object(tasks, "group", _fake_group):
        result = sync_root_scrapers_task()
    assert result["status"] == "Dispatched"
    assert set(result["stores"]) == {"provigo", "metro", "super_c"}
    with patch.object(tasks, "group", _fake_group):
        result = sync_root_scrapers_task(stores=["metro"])
    assert result["stores"] == ["metro"]


def test_sync_root_scrapers_task_none_configured():
    from app.services.scraper_bridge_service import ScraperBridgeService

    with patch.dict(ScraperBridgeService.SCRAPER_MAP, {}, clear=True):
        assert sync_root_scrapers_task() == {"status": "No root scrapers configured", "count": 0}


# ---------------------------------------------------------------------------
# cleanup_old_data_task
# ---------------------------------------------------------------------------

def test_cleanup_old_data_task():
    session = MagicMock()
    session.execute.side_effect = [
        SimpleNamespace(rowcount=2),
        SimpleNamespace(rowcount=1),
        SimpleNamespace(rowcount=0),
    ]
    with patch.object(tasks, "Session", lambda *a, **k: _FakeSessionCM(session)):
        result = cleanup_old_data_task()
    assert result == {
        "status": "Success", "logs_deleted": 2, "deals_deleted": 1, "prices_deleted": 0,
    }
    session.commit.assert_called_once()


def test_cleanup_old_data_task_error():
    session = MagicMock()
    session.execute.side_effect = RuntimeError("db down")
    with patch.object(tasks, "Session", lambda *a, **k: _FakeSessionCM(session)):
        result = cleanup_old_data_task()
    assert result == {"error": "db down"}


# ---------------------------------------------------------------------------
# generate_meal_plan_task
# ---------------------------------------------------------------------------

def _plan(days=None):
    return {
        "meal_plan": days if days is not None else [
            {"date": "2026-11-24", "day_name": "Monday", "breakfast": {}, "lunch": {}, "dinner": {}},
            {"date": "2026-11-25", "day_name": "Tuesday", "breakfast": {}, "lunch": {}, "dinner": {}},
        ],
        "shopping_summary": {"key_deals_used": []},
    }


class _FakePlanner:
    def __init__(self, session):
        pass

    def generate_plan(self, user, model_type=None):
        return _plan()


class _FakeNutritionAgent:
    def __init__(self, session):
        pass

    async def validate_plan(self, plan_data):
        return plan_data

    async def persist_daily_nutrition_from_plan(self, user_id, plan_data):
        return None


class _FailingNutritionAgent(_FakeNutritionAgent):
    async def validate_plan(self, plan_data):
        raise RuntimeError("nutrition down")


def _meal_plan_session(*, user=None, stores=None, total_active=50):
    session = MagicMock()
    store_result = SimpleNamespace(all=lambda: stores or [])
    count_result = SimpleNamespace(one=lambda: total_active)
    session.exec.side_effect = [store_result, count_result]
    session.get.return_value = user
    return session


def test_generate_meal_plan_task_user_not_found():
    session = _meal_plan_session(user=None)
    with patch.object(tasks, "Session", lambda *a, **k: _FakeSessionCM(session)):
        assert generate_meal_plan_task(99) == {"error": "User not found"}


def test_generate_meal_plan_task_happy_path():
    user = SimpleNamespace(id=1, household_size=2, postal_code="H4T1V6")
    session = _meal_plan_session(user=user)
    with patch.object(tasks, "Session", lambda *a, **k: _FakeSessionCM(session)), \
         patch.object(tasks, "MealPlannerAgent", _FakePlanner), \
         patch("app.agents.nutrition_agent.NutritionAgent", _FakeNutritionAgent), \
         patch.object(tasks.PantryService, "consume_from_plan_sync", return_value={}):
        result = generate_meal_plan_task(1)
    assert result["meal_plan"][0]["date"] == "2026-11-24"
    session.add.assert_called_once()
    session.commit.assert_called_once()


def test_generate_meal_plan_task_stale_and_low_deals_quick_refresh():
    user = SimpleNamespace(id=1, household_size=2, postal_code="H4T1V6")
    stores = [SimpleNamespace(chain="metro", is_stale=True)]
    session = _meal_plan_session(user=user, stores=stores, total_active=5)

    class _QuickScraper:
        def __init__(self, session, postal_code):
            pass

        async def scrape(self, stores, limit_per_store=30):
            return {"walmart": [{"name": "Deal"}], "metro": []}

        async def persist_deals(self, deals):
            return None

    async_session = MagicMock()
    with patch.object(tasks, "Session", lambda *a, **k: _FakeSessionCM(session)), \
         patch.object(tasks, "AsyncSession",
                      lambda *a, **k: _FakeAsyncSession(async_session)), \
         patch.object(tasks, "ScraperAgent", _QuickScraper), \
         patch.object(tasks, "scrape_task") as scrape_task_mock, \
         patch.object(tasks, "MealPlannerAgent", _FakePlanner), \
         patch("app.agents.nutrition_agent.NutritionAgent", _FakeNutritionAgent), \
         patch.object(tasks.PantryService, "consume_from_plan_sync", return_value={}):
        result = generate_meal_plan_task(1)
    assert result["meal_plan"][0]["date"] == "2026-11-24"
    scrape_task_mock.delay.assert_called_once_with(
        stores=["metro"], postal_code="H4T1V6"
    )


def test_generate_meal_plan_task_nutrition_failure_still_persists():
    user = SimpleNamespace(id=1, household_size=2, postal_code="H4T1V6")
    session = _meal_plan_session(user=user)
    with patch.object(tasks, "Session", lambda *a, **k: _FakeSessionCM(session)), \
         patch.object(tasks, "MealPlannerAgent", _FakePlanner), \
         patch("app.agents.nutrition_agent.NutritionAgent", _FailingNutritionAgent), \
         patch.object(tasks.PantryService, "consume_from_plan_sync", return_value={}):
        result = generate_meal_plan_task(1)
    assert result["meal_plan"][0]["date"] == "2026-11-24"


def test_generate_meal_plan_task_bad_start_date_and_days_key():
    class _DaysPlanner:
        def __init__(self, session):
            pass

        def generate_plan(self, user, model_type=None):
            return {"days": [{"date": "not-a-date"}], "shopping_summary": {}}

    user = SimpleNamespace(id=1, household_size=2, postal_code="H4T1V6")
    session = _meal_plan_session(user=user)
    with patch.object(tasks, "Session", lambda *a, **k: _FakeSessionCM(session)), \
         patch.object(tasks, "MealPlannerAgent", _DaysPlanner), \
         patch("app.agents.nutrition_agent.NutritionAgent", _FakeNutritionAgent), \
         patch.object(tasks.PantryService, "consume_from_plan_sync", return_value={}):
        result = generate_meal_plan_task(1)
    # Bad date falls back to today; the plan still persists.
    assert result["days"][0]["date"] == "not-a-date"
    meal_plan = session.add.call_args.args[0]
    assert meal_plan.start_date == date.today()
    assert (meal_plan.end_date - meal_plan.start_date).days == 6


def test_generate_meal_plan_task_pantry_failure_swallowed():
    user = SimpleNamespace(id=1, household_size=2, postal_code="H4T1V6")
    session = _meal_plan_session(user=user)
    with patch.object(tasks, "Session", lambda *a, **k: _FakeSessionCM(session)), \
         patch.object(tasks, "MealPlannerAgent", _FakePlanner), \
         patch("app.agents.nutrition_agent.NutritionAgent", _FakeNutritionAgent), \
         patch.object(tasks.PantryService, "consume_from_plan_sync",
                      side_effect=RuntimeError("pantry down")):
        result = generate_meal_plan_task(1)
    assert result["meal_plan"][0]["date"] == "2026-11-24"


def test_generate_meal_plan_task_no_days_defaults_to_today():
    class _EmptyPlanner:
        def __init__(self, session):
            pass

        def generate_plan(self, user, model_type=None):
            return {"meal_plan": [], "shopping_summary": {}}

    user = SimpleNamespace(id=1, household_size=2, postal_code="H4T1V6")
    session = _meal_plan_session(user=user)
    with patch.object(tasks, "Session", lambda *a, **k: _FakeSessionCM(session)), \
         patch.object(tasks, "MealPlannerAgent", _EmptyPlanner), \
         patch("app.agents.nutrition_agent.NutritionAgent", _FakeNutritionAgent), \
         patch.object(tasks.PantryService, "consume_from_plan_sync", return_value={}):
        result = generate_meal_plan_task(1)
    assert result["meal_plan"] == []
    meal_plan = session.add.call_args.args[0]
    assert meal_plan.start_date == date.today()


def test_generate_meal_plan_task_outer_error():
    class _BoomPlanner:
        def __init__(self, session):
            pass

        def generate_plan(self, user, model_type=None):
            raise RuntimeError("planner exploded")

    user = SimpleNamespace(id=1, household_size=2, postal_code="H4T1V6")
    session = _meal_plan_session(user=user)
    with patch.object(tasks, "Session", lambda *a, **k: _FakeSessionCM(session)), \
         patch.object(tasks, "MealPlannerAgent", _BoomPlanner):
        result = generate_meal_plan_task(1)
    assert result == {"error": "planner exploded"}


# ---------------------------------------------------------------------------
# send_daily_digests_task / send_user_digest_email_task
# ---------------------------------------------------------------------------

def test_send_daily_digests_no_users():
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
    )
    with patch.object(tasks, "AsyncSession",
                      lambda *a, **k: _FakeAsyncSession(session)):
        assert send_daily_digests_task() == {"status": "No users to notify"}


def test_send_daily_digests_dispatches():
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [1, 2]))
    )
    with patch.object(tasks, "AsyncSession",
                      lambda *a, **k: _FakeAsyncSession(session)), \
         patch.object(tasks, "send_user_digest_email_task") as digest_task:
        result = send_daily_digests_task()
    assert result == {"status": "Dispatched", "count": 2}
    assert digest_task.delay.call_count == 2


def test_send_daily_digests_error():
    session = MagicMock()
    session.execute = AsyncMock(side_effect=RuntimeError("db down"))
    with patch.object(tasks, "AsyncSession",
                      lambda *a, **k: _FakeAsyncSession(session)):
        assert send_daily_digests_task() == {"error": "db down"}


def _digest_session(user):
    session = MagicMock()
    session.get = AsyncMock(return_value=user)
    return session


def test_send_user_digest_email_task_user_missing_or_opted_out():
    for user in (None, SimpleNamespace(id=1, email_digest_enabled=False)):
        session = _digest_session(user)
        with patch.object(tasks, "AsyncSession",
                          lambda *a, **k: _FakeAsyncSession(session)):
            assert send_user_digest_email_task(1) == {"status": "User not found or opted out"}


def test_send_user_digest_email_task_no_deals():
    user = SimpleNamespace(id=1, email="a@b.c", email_digest_enabled=True, postal_code="H4T1V6")
    session = _digest_session(user)
    fake_deal_svc = MagicMock()
    fake_deal_svc.get_top_deals = AsyncMock(return_value=[])
    with patch.object(tasks, "AsyncSession",
                      lambda *a, **k: _FakeAsyncSession(session)), \
         patch.object(tasks, "DealService", return_value=fake_deal_svc):
        assert send_user_digest_email_task(1) == {"status": "No deals found", "email": "a@b.c"}


def test_send_user_digest_email_task_sends():
    user = SimpleNamespace(id=1, email="a@b.c", email_digest_enabled=True, postal_code="H4T1V6")
    session = _digest_session(user)
    fake_deal_svc = MagicMock()
    fake_deal_svc.get_top_deals = AsyncMock(return_value=[{"product": "Chicken"}])
    with patch.object(tasks, "AsyncSession",
                      lambda *a, **k: _FakeAsyncSession(session)), \
         patch.object(tasks, "DealService", return_value=fake_deal_svc), \
         patch.object(tasks.NotificationService, "send_daily_deals_digest",
                      new=AsyncMock()) as send_digest:
        result = send_user_digest_email_task(1)
    assert result == {"status": "Email sent", "email": "a@b.c"}
    send_digest.assert_awaited_once_with(user, [{"product": "Chicken"}])


def test_send_user_digest_email_task_error():
    session = MagicMock()
    session.get = AsyncMock(side_effect=RuntimeError("db down"))
    with patch.object(tasks, "AsyncSession",
                      lambda *a, **k: _FakeAsyncSession(session)):
        assert send_user_digest_email_task(1) == {"error": "db down"}
