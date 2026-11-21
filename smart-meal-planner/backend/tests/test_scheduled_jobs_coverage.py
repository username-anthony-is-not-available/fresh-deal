"""Coverage for app/scheduled_jobs.py.

Note (observed behaviour, not a fix): PantryItem has no expiration_date
column, so run_pantry_expiration_check always fails while building its
query; the outer handler logs the error and the function returns normally.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.scheduled_jobs as sj


@pytest.mark.asyncio
async def test_run_scheduled_scrape_success():
    with patch.object(sj, "scrape_task") as scrape_task, \
         patch.object(sj, "sync_root_scrapers_task") as sync_task, \
         patch.object(sj.NotificationService, "send_notification",
                      new=AsyncMock()) as notify:
        await sj.run_scheduled_scrape()
    scrape_task.delay.assert_called_once_with(postal_code="H4T1V6")
    sync_task.delay.assert_called_once_with(postal_code="H4T1V6")
    notify.assert_awaited_once()
    assert "Scheduled flyer refresh dispatched" in notify.call_args.args[0]


@pytest.mark.asyncio
async def test_run_scheduled_scrape_root_sync_skipped():
    # A failing root sync is only logged; the success notification still goes out.
    with patch.object(sj, "scrape_task") as scrape_task, \
         patch.object(sj, "sync_root_scrapers_task") as sync_task, \
         patch.object(sj.NotificationService, "send_notification",
                      new=AsyncMock()) as notify:
        sync_task.delay.side_effect = RuntimeError("no root scrapers")
        await sj.run_scheduled_scrape()
    scrape_task.delay.assert_called_once()
    assert "Scheduled flyer refresh dispatched" in notify.call_args.args[0]


@pytest.mark.asyncio
async def test_run_scheduled_scrape_dispatch_failure():
    with patch.object(sj, "scrape_task") as scrape_task, \
         patch.object(sj.NotificationService, "send_notification",
                      new=AsyncMock()) as notify:
        scrape_task.delay.side_effect = RuntimeError("broker down")
        await sj.run_scheduled_scrape()
    notify.assert_awaited_once()
    assert "Scrape job dispatch failed" in notify.call_args.args[0]


@pytest.mark.asyncio
async def test_run_pantry_expiration_check_query_fails():
    # PantryItem.expiration_date does not exist, so building the query raises
    # AttributeError inside the try; the handler logs it and returns normally.
    with patch.object(sj, "Session") as session_cls, \
         patch.object(sj.NotificationService, "send_notification",
                      new=AsyncMock()) as notify:
        session_cls.return_value.__enter__.return_value = MagicMock()
        await sj.run_pantry_expiration_check()
    notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_pantry_expiration_check_session_error():
    with patch.object(sj, "Session", side_effect=RuntimeError("db down")), \
         patch.object(sj.NotificationService, "send_notification",
                      new=AsyncMock()) as notify:
        await sj.run_pantry_expiration_check()
    notify.assert_not_awaited()


class _ExpiringItemsResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeColumn:
    """Stands in for a SQLAlchemy column in the stubbed query."""

    def is_not(self, other):
        return MagicMock()

    def __le__(self, other):
        return MagicMock()


def _patched_session(items):
    """A Session whose exec returns the given pantry items.

    The real query cannot run (PantryItem has no expiration_date column), so
    the statement builder and the model attribute are stubbed to reach the
    notification branch that would run once the column exists.
    """
    from types import SimpleNamespace

    session = MagicMock()
    session.exec.return_value = _ExpiringItemsResult(items)
    session_cls = MagicMock()
    session_cls.return_value.__enter__.return_value = session
    fake_pantry = SimpleNamespace(expiration_date=_FakeColumn())
    return session_cls, fake_pantry


@pytest.mark.asyncio
async def test_run_pantry_expiration_check_expiring_items():
    from types import SimpleNamespace

    items = [
        SimpleNamespace(user_id=1, name="Milk"),
        SimpleNamespace(user_id=1, name="Eggs"),
        SimpleNamespace(user_id=2, name="Yogurt"),
    ]
    session_cls, fake_pantry = _patched_session(items)
    with patch.object(sj, "Session", session_cls), \
         patch.object(sj, "select", return_value=MagicMock()), \
         patch.object(sj, "PantryItem", fake_pantry), \
         patch.object(sj.NotificationService, "send_notification",
                      new=AsyncMock()) as notify:
        await sj.run_pantry_expiration_check()
    assert notify.await_count == 2
    messages = [c.args[0] for c in notify.await_args_list]
    assert any("2 item(s) expiring soon (Milk, Eggs)" in m for m in messages)
    assert any("1 item(s) expiring soon (Yogurt)" in m for m in messages)


@pytest.mark.asyncio
async def test_run_pantry_expiration_check_many_items_truncated():
    from types import SimpleNamespace

    items = [SimpleNamespace(user_id=1, name=f"Item{i}") for i in range(7)]
    session_cls, fake_pantry = _patched_session(items)
    with patch.object(sj, "Session", session_cls), \
         patch.object(sj, "select", return_value=MagicMock()), \
         patch.object(sj, "PantryItem", fake_pantry), \
         patch.object(sj.NotificationService, "send_notification",
                      new=AsyncMock()) as notify:
        await sj.run_pantry_expiration_check()
    notify.assert_awaited_once()
    message = notify.call_args.args[0]
    assert "7 item(s) expiring soon" in message
    assert "Item4" in message
    assert "Item5" not in message  # only the first 5 names are listed


@pytest.mark.asyncio
async def test_run_pantry_expiration_check_no_items():
    session_cls, fake_pantry = _patched_session([])
    with patch.object(sj, "Session", session_cls), \
         patch.object(sj, "select", return_value=MagicMock()), \
         patch.object(sj, "PantryItem", fake_pantry), \
         patch.object(sj.NotificationService, "send_notification",
                      new=AsyncMock()) as notify:
        await sj.run_pantry_expiration_check()
    notify.assert_not_awaited()
