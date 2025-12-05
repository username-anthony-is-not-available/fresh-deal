
import os
import time
from playwright.sync_api import sync_playwright, expect

# Ensure directory exists
os.makedirs("tests/screenshots", exist_ok=True)

def verify_frontend(page):
    # 1. Navigate to Home
    page.goto("http://localhost:5173/")

    # Wait for the page to load
    page.wait_for_selector("h1")
    page.screenshot(path="tests/screenshots/1_onboarding.png")

    # 2. Onboard User
    page.get_by_placeholder("e.g. H4T 1V6").fill("H4T 1V6")
    page.get_by_role("combobox").nth(1).select_option("Vegetarian") # Select dietary pref
    page.get_by_role("button", name="Start Saving Today").click()

    # 3. Wait for navigation to /plan
    page.wait_for_url("**/plan")

    # Generate Plan if not already there
    try:
        if page.get_by_role("button", name="Generate My Plan").is_visible():
             page.get_by_role("button", name="Generate My Plan").click()
             # Capture Loading State
             page.wait_for_selector("text=AI is crafting your menu")
             page.screenshot(path="tests/screenshots/2_loading.png")

             # Wait for loading to finish and plan to appear
             page.wait_for_selector("text=Day 1", timeout=15000)
    except Exception as e:
        print(f"Plan generation step note: {e}")
        pass

    page.wait_for_timeout(2000) # Give it a moment to render cards
    page.screenshot(path="tests/screenshots/3_meal_plan_view.png")

    # 4. Zoomed view of a meal card (simulated by locator screenshot)
    # We will just take a shot of the first meal card
    try:
        first_card = page.locator(".bg-white.rounded-xl").first.locator(".bg-white").first
        if first_card.is_visible():
            first_card.screenshot(path="tests/screenshots/4_meal_card.png")
    except:
        pass

    # 5. Navigate to Shopping List
    page.get_by_role("link", name="Shopping List").click()
    page.wait_for_url("**/list")
    page.wait_for_selector("text=Shopping List")
    page.wait_for_timeout(1000)
    page.screenshot(path="tests/screenshots/5_shopping_list.png")

    # 6. Savings Comparison (part of shopping list page)
    try:
        savings_comp = page.locator("h2:has-text('Smart Savings')").locator("..")
        if savings_comp.is_visible():
             savings_comp.screenshot(path="tests/screenshots/7_savings_comparison.png")
    except:
        pass

    # 7. Navigate to Deals
    page.get_by_role("link", name="Deals").click()
    page.wait_for_url("**/deals")
    page.wait_for_selector("text=Weekly Flyers & Deals")

    # Ensure deals are loaded
    if page.get_by_text("No deals found").is_visible():
        page.get_by_text("Seed Mock Data").click()
        page.wait_for_selector("text=Found")

    page.wait_for_timeout(1000)
    page.screenshot(path="tests/screenshots/6_deals_browser.png")


if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Set viewport big enough for full view
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            verify_frontend(page)
            print("Verification script completed successfully. Screenshots in tests/screenshots/")
        except Exception as e:
            print(f"Verification failed: {e}")
            page.screenshot(path="tests/screenshots/error.png")
        finally:
            browser.close()
