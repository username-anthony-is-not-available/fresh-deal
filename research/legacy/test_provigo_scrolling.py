
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def test_provigo():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
        page = await context.new_page()

        await page.goto("https://www.provigo.ca/en/deals/flyer", wait_until="domcontentloaded")
        await asyncio.sleep(5)

        try:
            await page.click('#onetrust-accept-btn-handler', timeout=5000)
        except:
            pass

        try:
            await page.get_by_role("button", name="Yes").click(timeout=5000)
        except:
            pass

        try:
            await page.wait_for_selector('div.loading--spinner', state='hidden', timeout=20000)
        except:
            pass

        await asyncio.sleep(5)

        # Scroll
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 1000)")
            await asyncio.sleep(2)

        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')

        tiles = soup.select('[data-testid="product-grid-component"]')
        if not tiles:
            tiles = soup.select('div[class*="product-tile"]')

        print(f"Found {len(tiles)} Provigo tiles.")

        for tile in tiles[:5]:
            name_el = tile.select_one('[data-testid="product-title"]')
            price_el = tile.select_one('[data-testid="price-product-tile"]') or tile.select_one('[data-testid="sale-price"]')
            unit_el = tile.select_one('[data-testid="product-package-size"]')

            name = name_el.get_text() if name_el else "N/A"
            price = price_el.get_text() if price_el else "N/A"
            unit = unit_el.get_text() if unit_el else "N/A"

            print(f"  Name: {name}, Price: {price}, Unit: {unit}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_provigo())
