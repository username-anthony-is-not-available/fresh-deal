"""Tests for server-side caching of deal data (Issue #389)."""

from datetime import date, timedelta
import json
import time
import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel

from app.api.deals_export import get_weekly_summary
from app.api.endpoints import get_deal_cache_stats, list_deals
from app.models.all_models import Deal, Product, Store
from app.services.deal_cache_service import DealCacheService, deal_cache
from app.services.deal_service import DealService


class _FakeRedis:
    def __init__(self):
        self.store = {}

    def get(self, key: str):
        return self.store.get(key)

    def setex(self, key: str, ttl: int, value: str):
        self.store[key] = value

    def incr(self, key: str):
        val = int(self.store.get(key, 1)) + 1
        self.store[key] = str(val)
        return val


@pytest_asyncio.fixture
async def async_session():
    deal_cache.reset_stats()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    deal_cache.reset_stats()
    await engine.dispose()


def test_deal_cache_ttl_lru_eviction_and_version_invalidation(monkeypatch):
    """DealCacheService enforces TTL, bounded LRU eviction, and O(1) version invalidation."""
    fake_now = [100.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_now[0])

    cache = DealCacheService(ttl_seconds=10, max_entries=2)
    k1 = cache.build_key("deals", store="Metro")
    k2 = cache.build_key("deals", store="IGA")
    k3 = cache.build_key("deals", store="Maxi")

    cache.set(k1, [{"id": 1}])
    cache.set(k2, [{"id": 2}])
    # Touch k1 so k2 is least-recently-used
    assert cache.get(k1) == [{"id": 1}]
    cache.set(k3, [{"id": 3}])
    assert cache.get(k2) is None
    assert cache.get(k3) == [{"id": 3}]

    # Advance clock past TTL
    fake_now[0] += 11.0
    assert cache.get(k1) is None

    cache.set(k1, [{"id": 10}])
    old_version = cache.get_stats()["version"]
    new_version = cache.invalidate_deals()
    assert new_version == old_version + 1
    assert cache.get(k1) is None


def test_deal_cache_redis_l2_fallback_and_versioning():
    """DealCacheService reads/writes Redis L2 and increments Redis version key."""
    fake_redis = _FakeRedis()
    cache_writer = DealCacheService(ttl_seconds=60, redis_client=fake_redis)
    cache_reader = DealCacheService(ttl_seconds=60, redis_client=fake_redis)

    key = cache_writer.build_key("summary", scope="weekly")
    cache_writer.set(key, {"total_deals": 42})
    assert key in fake_redis.store
    assert json.loads(fake_redis.store[key]) == {"total_deals": 42}

    # Reader with empty in-memory store hits Redis L2 and promotes to local cache
    assert cache_reader.get(key) == {"total_deals": 42}

    v_after = cache_writer.invalidate_deals()
    assert v_after == 2
    assert cache_reader.build_key("summary", scope="weekly") != key


@pytest.mark.asyncio
async def test_list_deals_and_summary_cache_hits_and_auto_invalidation(async_session: AsyncSession):
    """Repeated read calls hit cache with zero SQL queries, and DB commits invalidate stale data."""
    today = date.today()
    store = Store(name="Metro Sherbrooke", chain="Metro", postal_code="J1H1A1")
    product = Product(name="Bananas", category="Produce", unit_type="kg")
    async_session.add_all([store, product])
    await async_session.commit()
    await async_session.refresh(store)
    await async_session.refresh(product)

    deal = Deal(
        product_id=product.id,
        store_id=store.id,
        price=1.49,
        original_price=2.49,
        discount_pct=40.0,
        valid_from=today - timedelta(days=1),
        valid_until=today + timedelta(days=5),
    )
    async_session.add(deal)
    await async_session.commit()

    select_count = 0

    def _on_query(conn, cursor, statement, parameters, context, executemany):
        nonlocal select_count
        if statement.lstrip().upper().startswith("SELECT"):
            select_count += 1

    sync_engine = async_session.bind.sync_engine
    event.listen(sync_engine, "before_cursor_execute", _on_query)
    try:
        # 1st call misses cache and queries DB
        first_deals = await list_deals(active_only=True, session=async_session)
        first_queries = select_count
        assert len(first_deals) == 1
        assert first_queries >= 1

        # 2nd identical call hits cache -> 0 additional SQL queries
        select_count = 0
        second_deals = await list_deals(active_only=True, session=async_session)
        assert len(second_deals) == 1
        assert second_deals[0]["product"].name == "Bananas"
        assert select_count == 0

        # Same for weekly summary and DealService.get_top_deals
        await get_weekly_summary(session=async_session)
        select_count = 0
        cached_summary = await get_weekly_summary(session=async_session)
        assert cached_summary["total_deals"] == 1
        assert select_count == 0

        await DealService(async_session).get_top_deals(limit=5)
        select_count = 0
        cached_top = await DealService(async_session).get_top_deals(limit=5)
        assert len(cached_top) == 1
        assert select_count == 0

        stats = await get_deal_cache_stats()
        assert stats["hits"] >= 3

        # Mutating a Deal automatically invalidates cache on commit
        product2 = Product(name="Apples", category="Produce", unit_type="kg")
        async_session.add(product2)
        await async_session.commit()
        await async_session.refresh(product2)

        deal2 = Deal(
            product_id=product2.id,
            store_id=store.id,
            price=2.99,
            original_price=4.99,
            discount_pct=40.0,
            valid_from=today - timedelta(days=1),
            valid_until=today + timedelta(days=5),
        )
        async_session.add(deal2)
        await async_session.commit()

        refreshed_deals = await list_deals(active_only=True, session=async_session)
        assert len(refreshed_deals) == 2
    finally:
        event.remove(sync_engine, "before_cursor_execute", _on_query)
