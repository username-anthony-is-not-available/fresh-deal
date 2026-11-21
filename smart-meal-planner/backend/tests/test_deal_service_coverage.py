"""Coverage for app/services/deal_service.py.

The session is faked; the deal cache is invalidated between tests so the
loader runs fresh each time.
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.deal_cache_service import deal_cache
from app.services.deal_service import DealService, _calc_loyalty_and_effective


@pytest.fixture(autouse=True)
def _clear_cache():
    deal_cache.invalidate_deals()
    yield
    deal_cache.invalidate_deals()


def _row(price=5.0, **deal_kw):
    today = date.today()
    deal = MagicMock()
    deal.price = price
    deal.original_price = deal_kw.get("original_price", 8.0)
    deal.discount_pct = deal_kw.get("discount_pct", 30)
    deal.loyalty_program = deal_kw.get("loyalty_program")
    deal.loyalty_points = deal_kw.get("loyalty_points")
    deal.sale_info = deal_kw.get("sale_info")
    deal.image_url = deal_kw.get("image_url")
    deal.valid_from = today - timedelta(days=1)
    deal.valid_until = today + timedelta(days=3)
    product = MagicMock()
    product.name = deal_kw.get("product_name", "Chicken Breast")
    product.category = "Meat"
    product.unit_type = "kg"
    store = MagicMock()
    store.name = deal_kw.get("store_name", "Metro")
    store.postal_code = deal_kw.get("postal_code", "H1H1H1")
    return (deal, product, store)


def _session_with_rows(rows):
    session = MagicMock()
    result = MagicMock()
    result.all.return_value = rows
    session.execute = AsyncMock(return_value=result)
    return session


# ---------------------------------------------------------------------------
# _calc_loyalty_and_effective
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("program,points,expected", [
    ("PC Optimum", 1000, (4.0, 1.0, False)),
    ("Optimum", 1000, (4.0, 1.0, False)),
    ("Scene+", 100, (4.0, 1.0, False)),
    ("Moi", 500, (1.0, 4.0, False)),
    ("AIR MILES", 10, (3.95, 1.05, False)),
    (None, 1000, (5.0, 0.0, False)),
    ("PC Optimum", 0, (5.0, 0.0, False)),
    ("Unknown Program", 1000, (5.0, 0.0, False)),
])
def test_calc_loyalty_programs(program, points, expected):
    assert _calc_loyalty_and_effective(5.0, program, points) == expected


def test_calc_loyalty_member_price():
    price, savings, is_member = _calc_loyalty_and_effective(
        10.0, "PC Optimum", 1000, sale_info="Member price 7.50 today"
    )
    # 1000 PC Optimum points ($1.00) plus the member-price gap ($2.50).
    assert (price, savings, is_member) == (7.50, 3.50, True)
    # Member price above the shelf price is not a member price.
    price, savings, is_member = _calc_loyalty_and_effective(
        5.0, None, None, sale_info="membre 9,99"
    )
    assert (price, savings, is_member) == (5.0, 0.0, False)
    # No member text at all.
    assert _calc_loyalty_and_effective(5.0, None, None, sale_info="regular sale") == (5.0, 0.0, False)
    # Loyalty savings never push the effective price below a cent.
    price, _, _ = _calc_loyalty_and_effective(1.0, "Scene+", 10000)
    assert price == 0.01


# ---------------------------------------------------------------------------
# DealService
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_active_deals_as_dicts():
    session = _session_with_rows([_row(price=5.0, loyalty_program="Moi", loyalty_points=500)])
    svc = DealService(session)
    deals = await svc.get_active_deals_as_dicts()
    assert len(deals) == 1
    d = deals[0]
    assert d["product"] == "Chicken Breast"
    assert d["store"] == "Metro"
    assert d["price"] == 5.0
    assert d["effective_price"] == 1.0  # 5.00 - 500 * 0.008
    assert d["loyalty_savings_cad"] == 4.0
    assert d["expires_in_days"] == 3
    assert d["unit"] == "kg"
    # Second call hits the cache and does not re-query.
    await svc.get_active_deals_as_dicts()
    assert session.execute.call_count == 1


@pytest.mark.asyncio
async def test_get_active_deals_empty():
    session = _session_with_rows([])
    svc = DealService(session)
    assert await svc.get_active_deals_as_dicts() == []


@pytest.mark.asyncio
async def test_get_top_deals_ranked_and_limited():
    rows = [
        _row(price=9.0, discount_pct=5, original_price=10.0, product_name="Expensive"),
        _row(price=5.0, discount_pct=50, original_price=10.0, product_name="Cheap"),
    ]
    session = _session_with_rows(rows)
    svc = DealService(session)
    top = await svc.get_top_deals(limit=1)
    assert len(top) == 1
    assert top[0]["product"] == "Cheap"
    assert top[0]["quality_score"] is not None


@pytest.mark.asyncio
async def test_get_top_deals_postal_code_filter():
    session = _session_with_rows([_row()])
    svc = DealService(session)
    top = await svc.get_top_deals(limit=10, postal_code="h2x1y2")
    assert len(top) == 1
    # The FSA filter was applied to the statement (no error, rows returned).
    assert session.execute.call_count == 1


@pytest.mark.asyncio
async def test_get_top_deals_empty():
    session = _session_with_rows([])
    svc = DealService(session)
    assert await svc.get_top_deals() == []
