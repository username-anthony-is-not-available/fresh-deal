"""Coverage for app/services/deal_quality_service.py.

Pure scoring logic plus the two static price-history helpers, exercised
with fabricated deals and fake sessions. No database or network involved.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.services.deal_quality_service import (
    DealQuality,
    DealQualityService,
    filter_quality_deals,
    score_deal,
)


def _deal(**kw):
    base = {
        "name": "Chicken Breast",
        "price": 8.0,
        "original_price": 10.0,
        "discount_pct": 20,
        "category": "meat",
        "unit": "kg",
    }
    base.update(kw)
    return base


def test_score_excellent_high_discount():
    svc = DealQualityService()
    score = svc.score_deal(_deal(discount_pct=45, price=8.0, original_price=15.0))
    assert score.quality == DealQuality.EXCELLENT
    assert score.overall_score >= 80
    assert score.adjustments["high_discount"] == 30


def test_score_discount_bands():
    svc = DealQualityService()
    assert svc.score_deal(_deal(discount_pct=35)).adjustments["good_discount"] == 20
    assert svc.score_deal(_deal(discount_pct=25)).adjustments["moderate_discount"] == 10
    assert svc.score_deal(_deal(discount_pct=15)).adjustments["small_discount"] == 5
    low = svc.score_deal(_deal(discount_pct=5))
    assert low.adjustments["minimal_discount"] == -5
    assert "Minimal discount (<10%)" in low.flags


def test_score_calculated_discount_from_prices():
    svc = DealQualityService()
    score = svc.score_deal(_deal(discount_pct=0, price=7.0, original_price=10.0))
    assert score.adjustments["calculated_discount"] == 15
    # Below 20% calculated discount adds nothing.
    score2 = svc.score_deal(_deal(discount_pct=0, price=9.5, original_price=10.0))
    assert "calculated_discount" not in score2.adjustments


def test_score_marketing_noise_in_name_and_sale_info():
    svc = DealQualityService()
    score = svc.score_deal(_deal(name="Watatow offre du siècle Chicken", sale_info="Méga vente!"))
    assert score.adjustments["marketing_noise_name"] == -20
    assert score.adjustments["marketing_noise_promo"] == -10
    assert any("Marketing noise" in f for f in score.flags)
    assert "Promotional marketing text in sale info" in score.flags


def test_score_suspicious_price_and_perpetual_sale():
    svc = DealQualityService()
    score = svc.score_deal(_deal(name="Rotisserie Chicken", price=0.10, category="meat"))
    assert score.adjustments["suspicious_price"] == -25
    assert score.adjustments["perpetual_sale"] == -15
    assert any("too low" in f for f in score.flags)
    assert "Product is frequently on perpetual 'sale'" in score.flags


def test_score_loyalty_value_bands():
    svc = DealQualityService()
    high = svc.score_deal(_deal(loyalty_points=3000, loyalty_program="Scene+"))
    assert high.adjustments["high_loyalty_value"] == 15
    mid = svc.score_deal(_deal(loyalty_points=100, loyalty_program="Moi"))
    assert mid.adjustments["moderate_loyalty_value"] == 5
    # Unknown program defaults to 0.001 per point.
    none = svc.score_deal(_deal(loyalty_points=10, loyalty_program="Unknown"))
    assert "high_loyalty_value" not in none.adjustments
    assert "moderate_loyalty_value" not in none.adjustments


def test_score_historical_below_and_at_average():
    svc = DealQualityService()
    below = svc.score_deal(_deal(price=7.0), historical_prices=[10.0, 10.0, 10.0])
    assert below.adjustments["below_historical_avg"] == 10
    at_avg = svc.score_deal(_deal(price=9.8), historical_prices=[10.0, 10.0, 10.0])
    assert at_avg.adjustments["at_historical_avg"] == -10
    assert "Price is near historical average (not a real sale)" in at_avg.flags
    # Fewer than 3 prices: no historical adjustment.
    few = svc.score_deal(_deal(price=7.0), historical_prices=[10.0, 10.0])
    assert "below_historical_avg" not in few.adjustments


def test_score_inflated_original_and_clamp():
    svc = DealQualityService()
    score = svc.score_deal(_deal(price=2.0, original_price=10.0, discount_pct=80))
    assert score.adjustments["inflated_original"] == -20
    assert "Original price may be inflated" in score.flags
    # Score never leaves 0-100 even with stacked penalties.
    worst = svc.score_deal(
        _deal(name="Watatow rotisserie chicken", price=0.05,
              original_price=50.0, discount_pct=1, category="meat")
    )
    assert 0 <= worst.overall_score <= 100
    assert worst.quality == DealQuality.NOISE


def test_score_quality_bands():
    svc = DealQualityService()
    assert svc.score_deal(_deal(discount_pct=45, price=8.0, original_price=15.0)).quality == DealQuality.EXCELLENT
    assert svc.score_deal(_deal(discount_pct=30)).quality == DealQuality.GOOD
    assert svc.score_deal(_deal(discount_pct=20)).quality == DealQuality.AVERAGE
    # 5% alone only drops to 45 (still AVERAGE); noise on top pushes it to POOR.
    assert svc.score_deal(_deal(discount_pct=5, price=8.0)).quality == DealQuality.AVERAGE
    assert svc.score_deal(_deal(discount_pct=5, name="Watatow chicken")).quality == DealQuality.POOR


def test_minimum_believable_price_units():
    svc = DealQualityService()
    assert svc._get_minimum_believable_price("beef", "kg") == 8.00
    assert svc._get_minimum_believable_price("beef", "lb") == pytest.approx(8.00 * 0.453592)
    assert svc._get_minimum_believable_price("dairy", "100g") == pytest.approx(0.075)
    assert svc._get_minimum_believable_price("dairy", "g") == pytest.approx(0.00075)
    # Unknown category falls back to the default minimum.
    assert svc._get_minimum_believable_price("unknown-category") == 0.50
    # First matching key wins (beef beats the generic meat entry).
    assert svc._get_minimum_believable_price("ground beef") == 8.00


def test_calculate_confidence():
    svc = DealQualityService()
    deal = _deal(valid_until="2026-12-31")
    assert svc._calculate_confidence(deal, []) == pytest.approx(0.95)
    # Flags reduce confidence; floor is 0.3.
    assert svc._calculate_confidence(deal, ["a"] * 20) == 0.3
    # Missing data lowers the base.
    assert svc._calculate_confidence({}, []) == 0.8


def test_filter_deals_thresholds():
    svc = DealQualityService()
    deals = [
        _deal(name="A", discount_pct=45, price=8.0, original_price=15.0),
        _deal(name="B", discount_pct=5, price=8.0),
        _deal(name="C", discount_pct=25),
    ]
    # B is the noisy low-value deal that must be dropped; A and C are kept.
    deals[1] = _deal(name="Watatow B", discount_pct=5, price=8.0)
    kept = svc.filter_deals(deals)
    names = [d["name"] for d in kept]
    assert "A" in names and "C" in names and "B" not in names
    assert kept[0]["quality_score"] is not None
    assert kept[0]["quality_level"] in ("excellent", "good", "average")
    # Stricter threshold keeps only the excellent one.
    assert [d["name"] for d in svc.filter_deals(deals, min_quality=DealQuality.EXCELLENT)] == ["A"]


def test_rank_deals_orders_and_limits():
    svc = DealQualityService()
    deals = [_deal(name="B", discount_pct=5), _deal(name="A", discount_pct=45, price=8.0, original_price=15.0)]
    ranked = svc.rank_deals(deals)
    assert ranked[0]["name"] == "A"
    assert ranked[1]["name"] == "B"
    assert svc.rank_deals(deals, top_n=1)[0]["name"] == "A"
    # Original dicts are not mutated by rank_deals.
    assert "quality_score" not in deals[0]


def test_remove_noise_and_summary():
    svc = DealQualityService()
    deals = [
        _deal(name="A", discount_pct=45, price=8.0, original_price=15.0),
        _deal(name="Watatow rotisserie chicken", price=0.05, original_price=50.0, discount_pct=1),
    ]
    kept = svc.remove_noise(deals)
    assert len(kept) == 1 and kept[0]["name"] == "A"
    summary = svc.get_quality_summary(deals)
    assert summary["total_deals"] == 2
    assert summary["excellent_deals"] == 1
    assert summary["noise_filtered"] == 1
    assert summary["average_score"] > 0
    assert summary["common_issues"]
    empty = svc.get_quality_summary([])
    assert empty["total_deals"] == 0
    assert empty["average_score"] == 0


def test_module_helpers():
    deal = _deal(name="A", discount_pct=45, price=8.0, original_price=15.0)
    out = score_deal(deal)
    assert out["quality_level"] == "excellent"
    assert out["quality_score"] >= 80
    deals = [_deal(name="A", discount_pct=45, price=8.0, original_price=15.0),
             _deal(name="B", discount_pct=5)]
    assert [d["name"] for d in filter_quality_deals(deals, "good")] == ["A"]
    # Unknown level falls back to AVERAGE, which keeps both A and B.
    assert [d["name"] for d in filter_quality_deals(deals, "bogus")] == ["A", "B"]
    assert [d["name"] for d in filter_quality_deals(deals, "noise")] == ["A", "B"]


def test_record_price_success_and_failure():
    session = MagicMock()
    DealQualityService.record_price(session, 1, 2, 9.99)
    session.add.assert_called_once()
    record = session.add.call_args[0][0]
    assert record.product_id == 1 and record.store_id == 2 and record.price == 9.99
    assert record.timestamp is not None
    # A failing session must not raise.
    failing = MagicMock()
    failing.add.side_effect = RuntimeError("db down")
    DealQualityService.record_price(failing, 1, 2, 9.99)
    # Explicit timestamp is honored.
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    DealQualityService.record_price(session, 1, 2, 1.0, timestamp=ts)
    assert session.add.call_args[0][0].timestamp == ts


def test_get_12_week_history_sync_async_and_plain():
    session = MagicMock()
    session.exec.return_value.all.return_value = [9.5, 10.0]
    assert DealQualityService.get_12_week_history(session, 1) == [9.5, 10.0]
    # store_id narrows the query (same result shape).
    assert DealQualityService.get_12_week_history(session, 1, store_id=3) == [9.5, 10.0]

    class AsyncOnlySession:
        def execute(self, stmt):
            result = MagicMock()
            result.scalars.return_value.all.return_value = [8.0]
            return result

    assert DealQualityService.get_12_week_history(AsyncOnlySession(), 1) == [8.0]
    # No exec/execute at all -> empty.
    assert DealQualityService.get_12_week_history(object(), 1) == []
    # A raising session -> empty, not an exception.
    failing = MagicMock()
    failing.exec.side_effect = RuntimeError("db down")
    assert DealQualityService.get_12_week_history(failing, 1) == []
