
import asyncio
import logging
from app.agents.scrapers.provigo_scraper import ProvigoScraper
from app.agents.scrapers.metro_scraper import MetroScraper
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def run_scraper(scraper_class, name):
    print(f"\n--- Running {name} Scraper ---")
    scraper = scraper_class(headless=True)
    deals = await scraper.scrape(limit=10)
    print(f"Found {len(deals)} deals for {name}")
    for i, deal in enumerate(deals[:3]):
        print(f"  {i+1}. {deal['name']} - {deal['price']} ({deal['unit']})")

    if not deals:
        print(f"FAILED to find deals for {name}. Check debug artifacts in /tmp")

async def main():
    # Ensure /tmp exists
    if not os.path.exists("/tmp"):
        os.makedirs("/tmp")

    # We'll temporarily monkeypatch the scrapers to use domcontentloaded for this test
    # so we can get better HTML artifacts if they were timing out.

    await run_scraper(ProvigoScraper, "Provigo")
    await run_scraper(MetroScraper, "Metro")

if __name__ == "__main__":
    asyncio.run(main())
