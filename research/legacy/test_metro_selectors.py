
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def test_metro():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://www.metro.ca/en/online-grocery/flyer", wait_until="domcontentloaded")
        await asyncio.sleep(10)

        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        tiles = soup.select('div.default-product-tile.tile-product')
        print(f"Found {len(tiles)} Metro tiles.")

        for tile in tiles[:3]:
            name = tile.select_one('span.head__title')
            price = tile.select_one('div.pricing__sale-price span.price-update')
            unit = tile.select_one('span.head__unit-details')
            print(f"  Name: {name.text if name else 'N/A'}, Price: {price.text if price else 'N/A'}, Unit: {unit.text if unit else 'N/A'}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_metro())
