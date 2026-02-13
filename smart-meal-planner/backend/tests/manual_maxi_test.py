
import asyncio
import logging
from app.agents.scrapers.maxi_scraper import MaxiScraper
import pprint

# Configure logging to see output from the scrapers
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def main():
    """
    Test script to run the Maxi scraper and print the results.
    """
    print("Starting Maxi scraper test...")
    # Use headless=True for the sandbox
    scraper = MaxiScraper(headless=True, postal_code="H2X 1Y1")

    deals = await scraper.scrape(limit=10)

    if deals:
        print(f"Successfully scraped {len(deals)} deals from {scraper.STORE_NAME}:")
        pprint.pprint(deals)
    else:
        print(f"No deals were scraped from {scraper.STORE_NAME}.")

if __name__ == "__main__":
    # This script needs to be run from the `smart-meal-planner/backend` directory
    # so that the module imports work correctly.
    asyncio.run(main())
