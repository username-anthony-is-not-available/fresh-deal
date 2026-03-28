
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

        # Handle cookie consent
        try:
            await page.click('#onetrust-accept-btn-handler', timeout=5000)
            print("Cookie accepted.")
        except:
            pass

        # Handle location popup
        try:
            # Look for "Yes" button in the pickup prompt
            yes_button = page.get_by_role("button", name="Yes")
            await yes_button.click(timeout=5000)
            print("Location confirmed.")
        except:
            print("Location popup not found.")

        # Wait for spinner to disappear
        try:
            await page.wait_for_selector('div.loading--spinner', state='hidden', timeout=20000)
            print("Spinner hidden.")
        except:
            pass

        await asyncio.sleep(10)

        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')

        # Try finding tiles
        tiles = soup.select('[data-testid="product-grid-component"]')
        if not tiles:
            tiles = soup.select('div[class*="product-tile"]')

        print(f"Found {len(tiles)} Provigo tiles.")

        for tile in tiles[:3]:
            name = tile.select_one('[data-testid="product-title"]')
            price = tile.select_one('[data-testid="price-product-tile"]') or tile.select_one('[data-testid="sale-price"]')
            unit = tile.select_one('[data-testid="product-package-size"]')

            print(f"  Name: {name.get_text() if name else 'N/A'}, Price: {price.get_text() if price else 'N/A'}, Unit: {unit.get_text() if unit else 'N/A'}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_provigo())
