import pytest
import os
import asyncio
import pytest_asyncio
from playwright.async_api import async_playwright
from app.agents.scrapers.iga_scraper import IgaScraper
from app.agents.scrapers.maxi_scraper import MaxiScraper
from app.agents.scrapers.super_c_scraper import SuperCScraper
from app.agents.scrapers.provigo_scraper import ProvigoScraper
from app.agents.scrapers.walmart_scraper import WalmartScraper
from app.agents.scrapers.metro_scraper import MetroScraper
from app.agents.scrapers.costco_scraper import CostcoScraper

# Constants for paths
SNAPSHOTS_DIR = os.path.join(os.path.dirname(__file__), "snapshots")

@pytest_asyncio.fixture
async def pw_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        yield page
        await browser.close()

async def setup_routing(page, main_snapshot: str, iframe_snapshot: str = None):
    main_path = os.path.join(SNAPSHOTS_DIR, main_snapshot)
    with open(main_path, "rb") as f:
        main_content = f.read()

    iframe_content = None
    if iframe_snapshot:
        iframe_path = os.path.join(SNAPSHOTS_DIR, iframe_snapshot)
        with open(iframe_path, "rb") as f:
            iframe_content = f.read()

    async def handle_route(route):
        url = route.request.url
        if any(domain in url for domain in ["iga.net", "maxi.ca", "superc.ca", "provigo.ca", "walmart.ca", "metro.ca", "costco.ca"]):
            await route.fulfill(body=main_content, content_type="text/html")
        elif "flipp.com/flyer" in url:
            if iframe_content:
                await route.fulfill(body=iframe_content, content_type="text/html")
            else:
                await route.fulfill(body="<html><body>No Iframe Content</body></html>", content_type="text/html")
        else:
            # Continue for other requests, but could also abort analytics
            if any(x in url for x in ["analytics", "google-analytics", "doubleclick"]):
                await route.abort()
            else:
                await route.continue_()

    await page.route("**/*", handle_route)

@pytest.mark.asyncio
async def test_iga_scraper_e2e(pw_page):
    await setup_routing(pw_page, "main_with_flipp.html", "iga_iframe.html")
    scraper = IgaScraper()
    scraper._random_delay = lambda min_d=0, max_d=0: asyncio.sleep(0)
    deals = await scraper._scrape_page(pw_page, limit=10)
    assert len(deals) >= 2
    assert any("Bananas" in d["name"] for d in deals)

@pytest.mark.asyncio
async def test_maxi_scraper_e2e(pw_page):
    await setup_routing(pw_page, "maxi_native.html")
    scraper = MaxiScraper()
    scraper._random_delay = lambda min_d=0, max_d=0: asyncio.sleep(0)
    scraper._handle_location = lambda p: asyncio.sleep(0)
    deals = await scraper._scrape_page(pw_page, limit=10)
    assert len(deals) >= 3
    assert any("Chicken Breast" in d["name"] for d in deals)

@pytest.mark.asyncio
async def test_super_c_scraper_e2e(pw_page):
    await setup_routing(pw_page, "main_with_flipp.html", "superc_iframe.html")
    scraper = SuperCScraper()
    scraper._random_delay = lambda min_d=0, max_d=0: asyncio.sleep(0)
    deals = await scraper._scrape_page(pw_page, limit=10)
    assert len(deals) >= 2
    assert any("Bananas" in d["name"] for d in deals)

@pytest.mark.asyncio
async def test_provigo_scraper_e2e(pw_page):
    await setup_routing(pw_page, "main_with_flipp.html", "provigo_iframe.html")
    scraper = ProvigoScraper()
    scraper._random_delay = lambda min_d=0, max_d=0: asyncio.sleep(0)
    deals = await scraper._scrape_page(pw_page, limit=10)
    assert len(deals) >= 1

@pytest.mark.asyncio
async def test_walmart_scraper_e2e(pw_page):
    await setup_routing(pw_page, "walmart_iframe.html")
    scraper = WalmartScraper()
    scraper._random_delay = lambda min_d=0, max_d=0: asyncio.sleep(0)
    scraper._handle_postal_code_modal = lambda p: asyncio.sleep(0)
    deals = await scraper._scrape_page(pw_page, limit=10)
    assert len(deals) >= 3
    assert any("Grapes" in d["name"] for d in deals)

@pytest.mark.asyncio
async def test_metro_scraper_e2e(pw_page):
    await setup_routing(pw_page, "metro_native.html")
    scraper = MetroScraper()
    scraper._random_delay = lambda min_d=0, max_d=0: asyncio.sleep(0)
    deals = await scraper._scrape_page(pw_page, limit=10)
    assert len(deals) >= 2
    assert any("Strawberries" in d["name"] for d in deals)

@pytest.mark.asyncio
async def test_costco_scraper_e2e(pw_page):
    await setup_routing(pw_page, "costco_native.html")
    scraper = CostcoScraper()
    scraper._random_delay = lambda min_d=0, max_d=0: asyncio.sleep(0)
    deals = await scraper._scrape_page(pw_page, limit=10)
    assert len(deals) >= 2
    assert any("Olive Oil" in d["name"] for d in deals)
