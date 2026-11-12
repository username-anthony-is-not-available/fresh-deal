"""Tests for database query optimizations and indexing on deals (Issue #384)."""

from datetime import date, datetime, timedelta, timezone
import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel

from app.agents.scraper_agent import ScraperAgent
from app.api.deals_export import get_best_deals, get_deals_data, get_weekly_summary
from app.api.endpoints import list_deals
from app.models.all_models import Deal, PriceRecord, Product, Store
from app.services.deal_service import DealService


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


def test_deal_models_define_expected_indexes():
    """Core deal query columns and composite lookup patterns must have SQL indexes."""
    deal_indexes = {idx.name for idx in Deal.__table__.indexes}
    product_indexes = {idx.name for idx in Product.__table__.indexes}
    store_indexes = {idx.name for idx in Store.__table__.indexes}
    price_indexes = {idx.name for idx in PriceRecord.__table__.indexes}

    assert "ix_deal_valid_window_discount" in deal_indexes
    assert "ix_deal_store_product_valid" in deal_indexes
    assert any("valid_until" in [c.name for c in idx.columns] for idx in Deal.__table__.indexes)
    assert any("discount_pct" in [c.name for c in idx.columns] for idx in Deal.__table__.indexes)
    assert any("category" in [c.name for c in idx.columns] for idx in Product.__table__.indexes)
    assert any("chain" in [c.name for c in idx.columns] for idx in Store.__table__.indexes)
    assert "ix_pricerecord_product_store_ts" in price_indexes


@pytest.mark.asyncio
async def test_list_deals_filters_sorts_and_paginates_in_sql(async_session: AsyncSession):
    """list_deals should accurately filter active deals, store, category, min_discount, and paginate."""
    today = date.today()
    s1 = Store(name="Metro Mont-Royal", chain="Metro", postal_code="H2J1X5")
    s2 = Store(name="IGA Rosemont", chain="IGA", postal_code="H1Y2Z1")
    p1 = Product(name="Chicken Breast", category="Meat", unit_type="kg")
    p2 = Product(name="Strawberries", category="Produce", unit_type="each")
    p3 = Product(name="Expired Milk", category="Dairy", unit_type="l")
    async_session.add_all([s1, s2, p1, p2, p3])
    await async_session.commit()
    for obj in (s1, s2, p1, p2, p3):
        await async_session.refresh(obj)

    d1 = Deal(
        product_id=p1.id,
        store_id=s1.id,
        price=9.99,
        original_price=19.99,
        discount_pct=50.0,
        valid_from=today - timedelta(days=1),
        valid_until=today + timedelta(days=5),
    )
    d2 = Deal(
        product_id=p2.id,
        store_id=s2.id,
        price=2.99,
        original_price=4.99,
        discount_pct=40.0,
        valid_from=today - timedelta(days=1),
        valid_until=today + timedelta(days=5),
    )
    d3 = Deal(
        product_id=p3.id,
        store_id=s1.id,
        price=3.49,
        original_price=4.99,
        discount_pct=30.0,
        valid_from=today - timedelta(days=14),
        valid_until=today - timedelta(days=7),
    )
    async_session.add_all([d1, d2, d3])
    await async_session.commit()

    active_deals = await list_deals(active_only=True, sort_by="discount_pct", session=async_session)
    assert [d["product"].name for d in active_deals] == ["Chicken Breast", "Strawberries"]

    meat_deals = await list_deals(category="Meat", store="Metro", min_discount=45.0, session=async_session)
    assert len(meat_deals) == 1
    assert meat_deals[0]["product"].name == "Chicken Breast"

    paged = await list_deals(active_only=True, sort_by="discount_pct", limit=1, offset=1, session=async_session)
    assert len(paged) == 1
    assert paged[0]["product"].name == "Strawberries"


@pytest.mark.asyncio
async def test_weekly_summary_sql_aggregation_and_best_deals(async_session: AsyncSession):
    """get_weekly_summary should return exact SQL-aggregated store/category counts, savings, and averages."""
    today = date.today()
    metro = Store(name="Metro Laval", chain="Metro", postal_code="H7T1A1")
    maxi = Store(name="Maxi Laval", chain="Maxi", postal_code="H7T1A2")
    apples = Product(name="Apples", category="Produce", unit_type="kg")
    beef = Product(name="Ground Beef", category="Meat", unit_type="kg")
    cheese = Product(name="Cheddar", category="Dairy", unit_type="each")
    async_session.add_all([metro, maxi, apples, beef, cheese])
    await async_session.commit()
    for obj in (metro, maxi, apples, beef, cheese):
        await async_session.refresh(obj)

    async_session.add_all(
        [
            Deal(
                product_id=apples.id,
                store_id=metro.id,
                price=2.0,
                original_price=4.0,
                discount_pct=50.0,
                valid_from=today,
                valid_until=today + timedelta(days=4),
            ),
            Deal(
                product_id=beef.id,
                store_id=metro.id,
                price=6.0,
                original_price=10.0,
                discount_pct=40.0,
                valid_from=today,
                valid_until=today + timedelta(days=4),
            ),
            Deal(
                product_id=cheese.id,
                store_id=maxi.id,
                price=4.0,
                original_price=5.0,
                discount_pct=20.0,
                valid_from=today,
                valid_until=today + timedelta(days=4),
            ),
        ]
    )
    await async_session.commit()

    summary = await get_weekly_summary(session=async_session)
    assert summary["total_deals"] == 3
    assert summary["stores"]["Metro"]["deal_count"] == 2
    assert summary["stores"]["Metro"]["total_savings"] == 6.0
    assert summary["stores"]["Metro"]["avg_discount"] == 45.0
    assert set(summary["stores"]["Metro"]["categories"]) == {"Produce", "Meat"}
    assert summary["categories"]["Produce"]["avg_discount"] == 50.0
    assert summary["top_categories"][0]["name"] == "Produce"

    best = await get_best_deals(limit=2, store=None, category=None, session=async_session)
    assert best["total_deals"] == 2
    assert [d["product_name"] for d in best["best_deals"]] == ["Apples", "Ground Beef"]

    top_from_service = await DealService(async_session).get_top_deals(limit=2)
    assert len(top_from_service) == 2


@pytest.mark.asyncio
async def test_persist_deals_avoids_n_plus_one_price_queries(async_session: AsyncSession):
    """persist_deals should issue a constant number of SELECT queries regardless of batch size."""
    query_count = 0

    def _count_queries(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        if statement.lstrip().upper().startswith("SELECT"):
            query_count += 1

    sync_engine = async_session.bind.sync_engine
    event.listen(sync_engine, "before_cursor_execute", _count_queries)
    try:
        agent = ScraperAgent(async_session)
        today = date.today()
        deals_batch = [
            {
                "name": f"Promo Item {i}",
                "store": "Metro",
                "category": "Produce",
                "price": 2.99 + i * 0.1,
                "original_price": 5.99 + i * 0.1,
                "valid_from": today,
                "valid_until": today + timedelta(days=6),
            }
            for i in range(25)
        ]

        query_count = 0
        await agent.persist_deals(deals_batch)

        # Constant prefetch queries (stores, products, existing deals, price records) — no N+1 per item
        assert query_count <= 6
    finally:
        event.remove(sync_engine, "before_cursor_execute", _count_queries)
