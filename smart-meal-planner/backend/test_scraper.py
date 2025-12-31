
import asyncio
import logging
from app.agents.scrapers.metro_scraper import MetroScraper
import pprint

# Configure logging to see output from the scrapers
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def main():
    """
    Test script to run a specific scraper and print the results.
    """
    print("Starting scraper test...")
    scraper = MetroScraper(headless=True)


    deals = await scraper.scrape(limit=20)

    if deals:
        print(f"Successfully scraped {len(deals)} deals from {scraper.STORE_NAME}:")
        pprint.pprint(deals)
    else:
        print(f"No deals were scraped from {scraper.STORE_NAME}.")

if __name__ == "__main__":
    # This script needs to be run from the `smart-meal-planner/backend` directory
    # so that the module imports work correctly.
    # Example: python3 test_scraper.py
    asyncio.run(main())
