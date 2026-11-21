"""Coverage for app/agents/scrapers/base_scraper.py.

Pure parsing helpers are tested directly; the async browser machinery is
tested with a fake Playwright/page so no real browser is launched.
"""

import json
import os
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.scrapers.base_scraper import (
    BaseScraper,
    calculate_effective_loyalty_price,
)


class ConcreteScraper(BaseScraper):
    async def _scrape_page(self, page, limit):
        return [{"name": "Test Deal", "price": 1.0}]


@pytest.fixture
def scraper(tmp_path):
    return ConcreteScraper(
        postal_code="H1H1H1",
        proxy_manager=MagicMock(),
        storage_path=str(tmp_path / "scrapers"),
    )


# ---------------------------------------------------------------------------
# Module-level loyalty helper
# ---------------------------------------------------------------------------

def test_calculate_effective_loyalty_price_member_only():
    price, savings = calculate_effective_loyalty_price(10.0, member_price=8.0)
    assert (price, savings) == (8.0, 2.0)


def test_calculate_effective_loyalty_price_member_above_price_ignored():
    price, savings = calculate_effective_loyalty_price(10.0, member_price=12.0)
    assert (price, savings) == (10.0, 0.0)


def test_calculate_effective_loyalty_price_loyalty_programs():
    # 1000 PC Optimum points = $1.00
    price, savings = calculate_effective_loyalty_price(
        10.0, loyalty_points=1000, loyalty_program="PC Optimum"
    )
    assert (price, savings) == (9.0, 1.0)
    # Scene+ is worth more per point.
    price, savings = calculate_effective_loyalty_price(
        10.0, loyalty_points=1000, loyalty_program="Scene+"
    )
    assert (price, savings) == (0.01, 10.0)
    # Moi points.
    price, savings = calculate_effective_loyalty_price(
        10.0, loyalty_points=500, loyalty_program="Moi"
    )
    assert (price, savings) == (6.0, 4.0)
    # AIR MILES.
    price, savings = calculate_effective_loyalty_price(
        10.0, loyalty_points=10, loyalty_program="AIR MILES"
    )
    assert price == pytest.approx(8.95)


def test_calculate_effective_loyalty_price_no_points_or_unknown_program():
    assert calculate_effective_loyalty_price(10.0) == (10.0, 0.0)
    assert calculate_effective_loyalty_price(10.0, loyalty_points=0, loyalty_program="Moi") == (10.0, 0.0)
    assert calculate_effective_loyalty_price(10.0, loyalty_points=100, loyalty_program="Nope") == (10.0, 0.0)
    # Member price plus points stack.
    price, savings = calculate_effective_loyalty_price(
        10.0, loyalty_points=1000, loyalty_program="PC Optimum", member_price=8.0
    )
    assert (price, savings) == (7.0, 3.0)


# ---------------------------------------------------------------------------
# Flyer week / cache
# ---------------------------------------------------------------------------

def test_get_flyer_week_id():
    # Thursday 2026-11-19 -> itself; Friday -> same Thursday; Wednesday -> prior Thursday.
    assert BaseScraper.get_flyer_week_id(datetime(2026, 11, 19)) == "2026_11_19"
    assert BaseScraper.get_flyer_week_id(datetime(2026, 11, 20)) == "2026_11_19"
    assert BaseScraper.get_flyer_week_id(datetime(2026, 11, 18)) == "2026_11_12"
    assert BaseScraper.get_flyer_week_id(datetime(2026, 11, 22)) == "2026_11_19"
    assert len(BaseScraper.get_flyer_week_id()) == 10  # default: today


def test_cache_path_and_roundtrip(scraper, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = scraper._get_cache_path()
    assert path.endswith(".json")
    assert "concrete_" in os.path.basename(path)
    assert os.path.isdir(os.path.join(str(tmp_path), ".cache", "flyers"))


def test_load_cached_payload_variants(scraper, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert scraper.load_cached_payload() is None
    cache_file = scraper._get_cache_path()
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump([{"name": "Deal"}], f)
    assert scraper.load_cached_payload() == [{"name": "Deal"}]
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump([], f)
    assert scraper.load_cached_payload() is None
    with open(cache_file, "w", encoding="utf-8") as f:
        f.write("{not json")
    assert scraper.load_cached_payload() is None
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump({"not": "a list"}, f)
    assert scraper.load_cached_payload() is None


def test_save_cached_payload_variants(scraper, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    scraper.save_cached_payload([])
    assert not os.path.exists(scraper._get_cache_path())
    scraper.save_cached_payload([{"name": "Deal"}])
    with open(scraper._get_cache_path(), encoding="utf-8") as f:
        assert json.load(f) == [{"name": "Deal"}]
    # A write failure is logged, not raised.
    with patch("builtins.open", side_effect=OSError("disk full")):
        scraper.save_cached_payload([{"name": "Deal"}])


def test_parse_html_default(scraper):
    assert scraper.parse_html("<html></html>") == []


# ---------------------------------------------------------------------------
# _parse_price
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("$2.99", 2.99),
    ("2,99$", 2.99),
    ("$ 3.50", 3.50),
    ("2 pour 5,00$", 2.50),
    ("2 for $5.00", 2.50),
    ("5$/2", 2.50),
    ("88¢", 0.88),
    ("88c", 0.88),
    ("4.99", 4.99),
    ("Prix: 12,49 $", 12.49),
    ("", None),
    (None, None),
    ("no price here", None),
    ("buy 1 get 1 free", None),
    ("2nd at 50% off", None),
    ("save $2.00 today", None),
    ("limit 2 per customer $3.99", 3.99),
    ("3 pour 0$", 0.0),  # zero total parses to a zero unit price
    ("0 pour 5$", 0.0),  # zero quantity falls through to the reverse pattern
    ("$5/0", 5.0),  # zero divisor falls through to the plain $ match
    ("$abc", None),
])
def test_parse_price(scraper, text, expected):
    assert scraper._parse_price(text) == expected


# ---------------------------------------------------------------------------
# _extract_unit / _parse_discount / _calculate_original_price
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Chicken 1kg pack", "kg"),
    ("Beef /kg", "kg"),
    ("par kg", "kg"),
    ("2lb roast", "lb"),
    ("pork /lb", "lb"),
    ("100g chocolate", "100g"),
    ("500 ml juice", "ml"),
    ("500ml juice", "each"),  # no word boundary before ml when glued to digits
    ("250 g butter", "g"),
    ("2 L milk", "L"),
    ("sac de riz", "sac/box"),
    ("boîte de conserve", "sac/box"),
    ("pqt de 12", "pack"),
    ("caisse de 24", "case"),
    ("bananas", "each"),
])
def test_extract_unit(scraper, text, expected):
    assert scraper._extract_unit(text) == expected


def test_parse_discount(scraper):
    assert scraper._parse_discount("Save 25% today") == 25.0
    assert scraper._parse_discount("no discount") is None
    assert scraper._parse_discount("") is None
    assert scraper._parse_discount(None) is None


def test_calculate_original_price(scraper):
    assert scraper._calculate_original_price(None, 25) == 0.0
    assert scraper._calculate_original_price(10.0, None) == 10.0
    assert scraper._calculate_original_price(10.0, 0) == 10.0
    assert scraper._calculate_original_price(7.50, 25) == 10.0


# ---------------------------------------------------------------------------
# _parse_loyalty_points / _categorize_product
# ---------------------------------------------------------------------------

def test_parse_loyalty_points(scraper):
    # NOTE: "2000" parses as 200 — the regex tries \d{1,3} before \d+, so
    # un-comma'd four-digit point values are truncated. Documented here as
    # observed behaviour, not fixed by this coverage change.
    assert scraper._parse_loyalty_points("Earn 2000 PC Optimum points") == ("PC Optimum", 200)
    assert scraper._parse_loyalty_points("Earn 1,000 Scene+ points") == ("Scene+", 1000)
    assert scraper._parse_loyalty_points("500 points Moi") == ("Moi", 500)
    assert scraper._parse_loyalty_points("no points here") is None
    assert scraper._parse_loyalty_points("") is None
    assert scraper._parse_loyalty_points(None) is None


@pytest.mark.parametrize("name,expected", [
    ("Orange Juice", "Beverages"),
    ("Potato Chips", "Snacks"),
    ("Chicken Breast", "Meat & Poultry"),
    # Dict order wins over the more specific category: "meat" matches first.
    ("Smoked Meat", "Meat & Poultry"),
    ("Salmon Fillet", "Seafood"),
    ("Banana", "Fruits"),
    ("Carrot", "Vegetables"),
    ("Milk 2%", "Dairy & Eggs"),
    # "cream" matches Dairy before Frozen is reached.
    ("Ice Cream", "Dairy & Eggs"),
    ("Baguette", "Bakery"),
    ("Basmati Rice", "Pantry"),
    ("Tofu", "International"),
    ("Paper Towel", "Household"),
    # "ham" inside "shampoo" matches Meat & Poultry first.
    ("Shampoo", "Meat & Poultry"),
    ("Mystery Widget", "Grocery"),
])
def test_categorize_product(scraper, name, expected):
    assert scraper._categorize_product(name) == expected


# ---------------------------------------------------------------------------
# _parse_flyer_dates
# ---------------------------------------------------------------------------

def test_parse_flyer_dates_patterns(scraper):
    assert scraper._parse_flyer_dates("from Jan 30 to Feb 5, 2024") == (date(2024, 1, 30), date(2024, 2, 5))
    assert scraper._parse_flyer_dates("du 30 janv. au 5 févr. 2024") == (date(2024, 1, 30), date(2024, 2, 5))
    assert scraper._parse_flyer_dates("from July 25 to 31, 2024") == (date(2024, 7, 25), date(2024, 7, 31))
    assert scraper._parse_flyer_dates("du 25 au 31 juillet 2024") == (date(2024, 7, 25), date(2024, 7, 31))
    assert scraper._parse_flyer_dates("from January 30 to February 5, 2024") == (date(2024, 1, 30), date(2024, 2, 5))
    assert scraper._parse_flyer_dates("") == (None, None)
    assert scraper._parse_flyer_dates("no dates here") == (None, None)
    assert scraper._parse_flyer_dates("du 30 février au 5 mars 2024") == (None, None)


# ---------------------------------------------------------------------------
# Async browser machinery (fake Playwright — no real browser is launched)
# ---------------------------------------------------------------------------

class _FakeContext:
    def __init__(self, page):
        self._page = page
        self.storage_state = AsyncMock()

    async def new_page(self):
        return self._page


class _FakeBrowser:
    def __init__(self, page):
        self._page = page
        self.close = AsyncMock()
        self.new_context_calls = []

    async def new_context(self, **kwargs):
        self.new_context_calls.append(kwargs)
        return _FakeContext(self._page)


class _FakeChromium:
    def __init__(self, browser, launch_error=None):
        self._browser = browser
        self._launch_error = launch_error
        self.launch_calls = []

    async def launch(self, **kwargs):
        self.launch_calls.append(kwargs)
        if self._launch_error is not None:
            raise self._launch_error
        return self._browser


class _FakePlaywright:
    def __init__(self, browser, launch_error=None):
        self.chromium = _FakeChromium(browser, launch_error)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _fake_page(**overrides):
    page = MagicMock()
    page.viewport_size = {"width": 800, "height": 600}
    page.url = "https://example.com/flyer"
    page.mouse.move = AsyncMock()
    page.type = AsyncMock()
    page.is_visible = AsyncMock(return_value=False)
    page.locator.return_value.click = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.evaluate = AsyncMock(return_value=1000)
    page.screenshot = AsyncMock()
    page.content = AsyncMock(return_value="<html></html>")
    for key, value in overrides.items():
        setattr(page, key, value)
    return page


@pytest.fixture
def _fake_pw(monkeypatch):
    """Install a fake async_playwright; returns (playwright, browser, page)."""
    page = _fake_page()
    browser = _FakeBrowser(page)
    pw = _FakePlaywright(browser)

    def _factory():
        return pw

    monkeypatch.setattr(
        "app.agents.scrapers.base_scraper.async_playwright", _factory
    )
    monkeypatch.setattr(
        "app.agents.scrapers.base_scraper.stealth_async", None
    )
    return pw, browser, page


@pytest.mark.asyncio
async def test_scrape_cache_hit_returns_without_browser(scraper, monkeypatch):
    monkeypatch.setattr(
        scraper, "load_cached_payload",
        lambda: [{"name": "Cached"}, {"name": "Cached 2"}],
    )
    deals, proxy, shot, html = await scraper.scrape(limit=1)
    assert deals == [{"name": "Cached"}]
    assert proxy == "disk_cache"
    assert shot is None and html is None


@pytest.mark.asyncio
async def test_scrape_happy_path(scraper, tmp_path, monkeypatch, _fake_pw):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scraper, "load_cached_payload", lambda: None)
    monkeypatch.setattr(scraper, "_simulate_mouse_movement", AsyncMock())
    monkeypatch.setattr(scraper, "_check_incapsula_block", AsyncMock(return_value=False))
    scraper.proxy_manager.get_proxy.return_value = "http://proxy:8080"
    deals, proxy, shot, html = await scraper.scrape(limit=10)
    assert deals == [{"name": "Test Deal", "price": 1.0}]
    assert proxy == "http://proxy:8080"
    assert shot is None and html is None
    # Deals were cached to disk.
    cache_file = scraper._get_cache_path()
    assert os.path.exists(cache_file)
    with open(cache_file, encoding="utf-8") as f:
        assert json.load(f) == [{"name": "Test Deal", "price": 1.0}]


@pytest.mark.asyncio
async def test_scrape_incapsula_block(scraper, tmp_path, monkeypatch, _fake_pw):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scraper, "load_cached_payload", lambda: None)
    monkeypatch.setattr(scraper, "_simulate_mouse_movement", AsyncMock())
    monkeypatch.setattr(scraper, "_check_incapsula_block", AsyncMock(return_value=True))
    scraper.proxy_manager.get_proxy.return_value = "http://proxy:8080"
    with pytest.raises(Exception, match=r"\[BOT_BLOCK\]"):
        await scraper.scrape()
    scraper.proxy_manager.blacklist_proxy.assert_called_with("http://proxy:8080")
    assert scraper.last_screenshot is not None
    assert scraper.last_html is not None


@pytest.mark.asyncio
async def test_scrape_timeout_error_tagged(scraper, tmp_path, monkeypatch, _fake_pw):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scraper, "load_cached_payload", lambda: None)
    monkeypatch.setattr(scraper, "_simulate_mouse_movement", AsyncMock())

    async def _boom(page, limit):
        raise Exception("Timeout waiting for selector")

    monkeypatch.setattr(scraper, "_scrape_page", _boom)
    with pytest.raises(Exception, match=r"\[TIMEOUT\]"):
        await scraper.scrape()


@pytest.mark.asyncio
async def test_scrape_generic_error_blacklists_proxy(scraper, tmp_path, monkeypatch, _fake_pw):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scraper, "load_cached_payload", lambda: None)
    monkeypatch.setattr(scraper, "_simulate_mouse_movement", AsyncMock())
    scraper.proxy_manager.get_proxy.return_value = "http://proxy:8080"

    async def _boom(page, limit):
        raise ValueError("structure changed")

    monkeypatch.setattr(scraper, "_scrape_page", _boom)
    with pytest.raises(ValueError, match="structure changed"):
        await scraper.scrape()
    scraper.proxy_manager.blacklist_proxy.assert_called_with("http://proxy:8080")


@pytest.mark.asyncio
async def test_scrape_artifact_save_failure_is_logged_not_raised(scraper, tmp_path, monkeypatch, _fake_pw):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scraper, "load_cached_payload", lambda: None)
    monkeypatch.setattr(scraper, "_simulate_mouse_movement", AsyncMock())
    monkeypatch.setattr(
        scraper, "_save_debug_artifacts",
        AsyncMock(side_effect=RuntimeError("disk full")),
    )

    async def _boom(page, limit):
        raise ValueError("structure changed")

    monkeypatch.setattr(scraper, "_scrape_page", _boom)
    with pytest.raises(ValueError, match="structure changed"):
        await scraper.scrape()


@pytest.mark.asyncio
async def test_scrape_incapsula_message_without_tag_gets_tagged(scraper, tmp_path, monkeypatch, _fake_pw):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scraper, "load_cached_payload", lambda: None)
    monkeypatch.setattr(scraper, "_simulate_mouse_movement", AsyncMock())

    async def _boom(page, limit):
        raise Exception("Incapsula incident detected")

    monkeypatch.setattr(scraper, "_scrape_page", _boom)
    with pytest.raises(Exception, match=r"\[BOT_BLOCK\] Incapsula"):
        await scraper.scrape()


@pytest.mark.asyncio
async def test_scrape_browser_launch_failure(scraper, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scraper, "load_cached_payload", lambda: None)
    page = _fake_page()
    browser = _FakeBrowser(page)
    pw = _FakePlaywright(browser, launch_error=RuntimeError("no chromium"))
    monkeypatch.setattr(
        "app.agents.scrapers.base_scraper.async_playwright", lambda: pw
    )
    scraper.proxy_manager.get_proxy.return_value = "http://proxy:8080"
    with pytest.raises(RuntimeError, match="no chromium"):
        await scraper.scrape()
    scraper.proxy_manager.blacklist_proxy.assert_called_with("http://proxy:8080")


@pytest.mark.asyncio
async def test_scrape_no_deals_skips_cache(scraper, tmp_path, monkeypatch, _fake_pw):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scraper, "load_cached_payload", lambda: None)
    monkeypatch.setattr(scraper, "_simulate_mouse_movement", AsyncMock())
    monkeypatch.setattr(scraper, "_check_incapsula_block", AsyncMock(return_value=False))

    async def _empty(page, limit):
        return []

    monkeypatch.setattr(scraper, "_scrape_page", _empty)
    deals, _, _, _ = await scraper.scrape()
    assert deals == []
    assert not os.path.exists(scraper._get_cache_path())


@pytest.mark.asyncio
async def test_get_browser_with_and_without_proxy(scraper, _fake_pw):
    pw, browser, _ = _fake_pw
    launched = await scraper._get_browser(pw, "http://proxy:8080")
    assert launched is browser
    assert pw.chromium.launch_calls[0]["proxy"] == {"server": "http://proxy:8080"}
    await scraper._get_browser(pw, None)
    assert pw.chromium.launch_calls[1]["proxy"] is None
    assert pw.chromium.launch_calls[1]["headless"] is True


@pytest.mark.asyncio
async def test_get_context_uses_storage_state_when_present(scraper, tmp_path, monkeypatch, _fake_pw):
    _, browser, _ = _fake_pw
    # No storage state file -> storage_state=None.
    ctx = await scraper._get_context(browser)
    assert browser.new_context_calls[0]["storage_state"] is None
    assert browser.new_context_calls[0]["locale"] == "en-CA"
    # With a storage state file present, its path is passed through.
    with open(scraper.storage_state_path, "w", encoding="utf-8") as f:
        f.write("{}")
    ctx = await scraper._get_context(browser)
    assert browser.new_context_calls[1]["storage_state"] == scraper.storage_state_path


@pytest.mark.asyncio
async def test_get_page_applies_stealth_when_available(scraper, monkeypatch):
    applied = []

    async def _stealth(page):
        applied.append(page)

    monkeypatch.setattr("app.agents.scrapers.base_scraper.stealth_async", _stealth)
    page = _fake_page()
    context = _FakeContext(page)
    got = await scraper._get_page(context)
    assert got is page
    assert applied == [page]


@pytest.mark.asyncio
async def test_random_delay_uses_asyncio_sleep(scraper, monkeypatch):
    calls = []

    async def _sleep(delay):
        calls.append(delay)

    monkeypatch.setattr("asyncio.sleep", _sleep)
    monkeypatch.setattr("random.uniform", lambda a, b: 2.25)
    await scraper._random_delay(1.5, 3.0)
    assert calls == [2.25]


@pytest.mark.asyncio
async def test_simulate_mouse_movement(scraper, monkeypatch):
    page = _fake_page()
    monkeypatch.setattr(scraper, "_random_delay", AsyncMock())
    monkeypatch.setattr("random.uniform", lambda a, b: 10.0)
    monkeypatch.setattr("random.randint", lambda a, b: 2)
    await scraper._simulate_mouse_movement(page)
    assert page.mouse.move.call_count == 10
    page2 = _fake_page()
    page2.viewport_size = None
    await scraper._simulate_mouse_movement(page2)
    assert page2.mouse.move.call_count == 0


@pytest.mark.asyncio
async def test_type_with_random_delay(scraper, monkeypatch):
    page = _fake_page()
    monkeypatch.setattr(scraper, "_random_delay", AsyncMock())
    await scraper._type_with_random_delay(page, "#search", "abc")
    assert page.type.call_count == 3
    assert page.type.call_args_list[0].args == ("#search", "a")


@pytest.mark.asyncio
async def test_handle_cookie_consent(scraper):
    page = _fake_page()
    page.is_visible = AsyncMock(return_value=True)
    assert await scraper._handle_cookie_consent(page, "#accept") is True
    page.locator.assert_called_with("#accept")
    page.wait_for_load_state.assert_called_once()
    page2 = _fake_page()
    assert await scraper._handle_cookie_consent(page2, "#accept") is False
    page3 = _fake_page()
    page3.is_visible = AsyncMock(side_effect=RuntimeError("gone"))
    assert await scraper._handle_cookie_consent(page3, "#accept") is False


@pytest.mark.asyncio
async def test_scroll_to_bottom(scraper, monkeypatch):
    page = _fake_page()
    monkeypatch.setattr(scraper, "_random_delay", AsyncMock())
    page.evaluate = AsyncMock(side_effect=[1000, 1000, 1000])
    await scraper._scroll_to_bottom(page, max_scrolls=5)
    assert page.evaluate.call_count == 3
    page2 = _fake_page()
    page2.evaluate = AsyncMock(side_effect=[1000, 2000, 2000, 2000, 2000])
    await scraper._scroll_to_bottom(page2, max_scrolls=5)
    assert page2.evaluate.call_count == 5


@pytest.mark.asyncio
async def test_save_debug_artifacts(scraper, tmp_path):
    page = _fake_page()
    page.content = AsyncMock(return_value="<html>debug</html>")
    shot, html = await scraper._save_debug_artifacts(page, "testcase")
    assert shot is not None and html is not None
    assert shot.endswith(".png") and html.endswith(".html")
    page.screenshot.assert_called_once_with(path=shot)
    with open(html, encoding="utf-8") as f:
        assert f.read() == "<html>debug</html>"
    failing = _fake_page()
    failing.screenshot = AsyncMock(side_effect=RuntimeError("no shot"))
    assert await scraper._save_debug_artifacts(failing, "testcase") == (None, None)


@pytest.mark.asyncio
async def test_check_incapsula_block(scraper):
    blocked = _fake_page()
    blocked.content = AsyncMock(return_value="Incapsula incident ID 12345")
    assert await scraper._check_incapsula_block(blocked) is True
    clean = _fake_page()
    assert await scraper._check_incapsula_block(clean) is False
    broken = _fake_page()
    broken.content = AsyncMock(side_effect=RuntimeError("gone"))
    assert await scraper._check_incapsula_block(broken) is False


@pytest.mark.asyncio
async def test_scrape_flipp_frame_success_and_timeout(scraper):
    html = (
        '<div data-testid="product-tile">A</div>'
        '<div data-testid="product-tile">B</div>'
    )
    tile_locator = MagicMock()
    tile_locator.first.wait_for = AsyncMock()
    frame = MagicMock()
    frame.locator.return_value = tile_locator
    frame.locator.return_value.inner_html = AsyncMock(return_value=html)
    page = _fake_page()
    page.frame_locator.return_value = frame
    # locator('html') must return the inner_html mock, not the tile locator.
    frame.locator.side_effect = lambda sel: (
        tile_locator if sel != "html" else MagicMock(inner_html=AsyncMock(return_value=html))
    )
    tiles = await scraper._scrape_flipp_frame(page)
    assert len(tiles) == 2

    failing = _fake_page()
    failing.wait_for_selector = AsyncMock(side_effect=TimeoutError("slow"))
    assert await scraper._scrape_flipp_frame(failing) == []
