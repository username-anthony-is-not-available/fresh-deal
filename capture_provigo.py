
import asyncio
from playwright.async_api import async_playwright

async def capture_provigo():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
        page = await context.new_page()

        url = "https://www.provigo.ca/en/flyer"
        print(f"Navigating to {url}...")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # Handle cookie consent if it appears
        try:
            await page.wait_for_selector('#onetrust-accept-btn-handler', timeout=10000)
            await page.click('#onetrust-accept-btn-handler')
            print("Cookie consent accepted.")
        except:
            print("Cookie consent not found or already accepted.")

        # Wait for spinner to disappear
        print("Waiting for spinner to disappear...")
        try:
            await page.wait_for_selector('div.loading--spinner', state='hidden', timeout=30000)
            print("Spinner disappeared.")
        except:
            print("Spinner still visible or not found.")

        # Wait a bit more for content
        await asyncio.sleep(10)

        # Save HTML and Screenshot
        html_path = "/tmp/provigo_full_load.html"
        png_path = "/tmp/provigo_full_load.png"

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(await page.content())
        await page.screenshot(path=png_path)

        print(f"Saved artifacts to {html_path} and {png_path}")

        # Check for tiles
        content = await page.content()
        if 'data-testid="product-title"' in content:
            print("Found data-testid='product-title'")
        if 'product-tile' in content:
            print("Found 'product-tile'")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_provigo())
