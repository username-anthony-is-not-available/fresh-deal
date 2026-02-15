import pytest
import os
import asyncio
from playwright.async_api import Page, async_playwright
from app.agents.scrapers.iga_scraper import IgaScraper
from app.agents.scrapers.super_c_scraper import SuperCScraper
from app.agents.scrapers.maxi_scraper import MaxiScraper
from app.agents.scrapers.provigo_scraper import ProvigoScraper
from app.agents.scrapers.walmart_scraper import WalmartScraper

SNAPSHOTS_DIR = os.path.join(os.path.dirname(__file__), "snapshots")

async def setup_routing(page: Page):
    """
    Sets up Playwright routing to serve local snapshots.
    """
    async def handle_route(route, request):
        url = request.url

        # Determine which snapshot to serve
        filename = None
        if "iga.net" in url and "online-flyer" in url:
            filename = "iga_main.html"
        elif "iga_iframe" in url or "flipp.com" in url and "iga" in url:
            filename = "iga_iframe.html"
        elif "superc.ca" in url and "flyer" in url:
            filename = "superc_main.html"
        elif "superc_iframe" in url or "flipp.com" in url and "superc" in url:
            filename = "superc_iframe.html"
        elif "maxi.ca" in url:
            filename = "maxi_native.html" # For simplicity, Maxi test uses native
        elif "provigo.ca" in url:
            if "flyer" in url or "deals" in url:
                filename = "provigo_main.html"
        elif "provigo_iframe" in url or "flipp.com" in url and "provigo" in url:
            filename = "provigo_iframe.html"
        elif "walmart.ca" in url and "flyer" in url:
            filename = "walmart_main.html"

        if filename:
            filepath = os.path.join(SNAPSHOTS_DIR, filename)
            if os.path.exists(filepath):
                await route.fulfill(path=filepath)
                return

        await route.continue_()

    await page.route("**/*", handle_route)

@pytest.mark.asyncio
async def test_iga_scraper_e2e():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        await setup_routing(page)

        scraper = IgaScraper()
        # Mock _random_delay to speed up tests
        scraper._random_delay = lambda min_d, max_d: asyncio.sleep(0)

        deals = await scraper._scrape_page(page, limit=10)

        assert len(deals) > 0
        assert any("Bananas" in d["name"] for d in deals)
        assert any(d["price"] == 0.79 for d in deals)

        await browser.close()

@pytest.mark.asyncio
async def test_super_c_scraper_e2e():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        await setup_routing(page)

        scraper = SuperCScraper()
        scraper._random_delay = lambda min_d, max_d: asyncio.sleep(0)

        deals = await scraper._scrape_page(page, limit=10)

        assert len(deals) > 0
        assert any("Ground Beef" in d["name"] for d in deals)
        assert any(d["price"] == 5.99 for d in deals)

        await browser.close()

@pytest.mark.asyncio
async def test_provigo_scraper_e2e():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        await setup_routing(page)

        scraper = ProvigoScraper()
        scraper._random_delay = lambda min_d, max_d: asyncio.sleep(0)

        deals = await scraper._scrape_page(page, limit=10)

        assert len(deals) > 0
        assert any("Chicken Breasts" in d["name"] for d in deals)
        assert any(d["price"] == 12.99 for d in deals)

        await browser.close()

@pytest.mark.asyncio
async def test_walmart_scraper_e2e():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        await setup_routing(page)

        scraper = WalmartScraper()
        scraper._random_delay = lambda min_d, max_d: asyncio.sleep(0)

        deals = await scraper._scrape_page(page, limit=10)

        assert len(deals) > 0
        assert any("Grapes" in d["name"] for d in deals)
        assert any(d["price"] == 2.97 for d in deals)

        await browser.close()

@pytest.mark.asyncio
async def test_maxi_scraper_e2e():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        await setup_routing(page)

        scraper = MaxiScraper()
        scraper._random_delay = lambda min_d, max_d: asyncio.sleep(0)

        deals = await scraper._scrape_page(page, limit=10)

        assert len(deals) > 0
        assert any("Chicken Breast" in d["name"] for d in deals)
        assert any(d["price"] == 12.99 for d in deals)

        await browser.close()
