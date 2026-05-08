
import asyncio
from playwright.async_api import async_playwright

async def test_provigo():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
        page = await context.new_page()

        await page.goto("https://www.provigo.ca/en/flyer", wait_until="domcontentloaded")
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

        await asyncio.sleep(10)

        # Check for iframe
        iframe = page.frame_locator('iframe[title="Main Panel"]')
        tiles_count = await iframe.locator('div[data-testid="product-tile"]').count()
        print(f"Found {tiles_count} tiles in Flipp iframe.")

        if tiles_count == 0:
            content = await page.content()
            if "Main Panel" not in content:
                print("Main Panel iframe not found in content.")
            else:
                print("Main Panel iframe found in content but locator failed.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_provigo())
