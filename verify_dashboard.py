from playwright.sync_api import Page, expect, sync_playwright
import time

def test_scraping_dashboard(page: Page):
    page.goto("http://localhost:5173/login")

    # Fill login form
    page.fill('input[type="email"]', "test@example.com")
    page.fill('input[type="password"]', "password")
    page.click('button:has-text("Login")')

    # Wait for navigation to home or deals
    time.sleep(3)

    # Navigate to scraping
    page.goto("http://localhost:5173/scraping")
    time.sleep(3)

    # Take a screenshot
    page.screenshot(path="/home/jules/verification/scraping_dashboard.png", full_page=True)

    # Verify Adonis and Costco are present
    expect(page.get_by_text("Adonis")).to_have_count(2)
    expect(page.get_by_text("Costco")).to_have_count(2)

    print("Verification successful: Adonis and Costco found on the dashboard.")

if __name__ == "__main__":
    import os
    os.makedirs("/home/jules/verification", exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            test_scraping_dashboard(page)
        except Exception as e:
            print(f"Error during verification: {e}")
            page.screenshot(path="/home/jules/verification/error.png")
        finally:
            browser.close()
