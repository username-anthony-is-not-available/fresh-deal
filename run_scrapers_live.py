import asyncio
import logging
from src.scrapers.provigo_scraper import ProvigoScraper
import os
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def run_scraper(scraper_class, name):
    print(f"\n--- Running {name} Scraper ---")
    scraper = scraper_class(headless=True)
    try:
        deals = await scraper.scrape(limit=10)
        print(f"Found {len(deals)} deals for {name}")
        for i, deal in enumerate(deals[:3]):
            print(f"  {i+1}. {deal.name} - ${deal.price:.2f} ({deal.unit})")

        if not deals:
            print(f"FAILED to find deals for {name}. Check debug artifacts in /tmp/scrapers")
    except Exception as e:
        print(f"ERROR running scraper {name}: {e}")

async def main():
    # Scrapers to run
    scrapers = [
        (ProvigoScraper, "Provigo"),
        # Add more scrapers here as they are refactored
    ]

    for scraper_class, name in scrapers:
        await run_scraper(scraper_class, name)

if __name__ == "__main__":
    asyncio.run(main())
