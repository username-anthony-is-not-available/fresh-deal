import asyncio
import sys
import os
import logging
from typing import Dict, Any

# Add the backend directory to sys.path so we can import app
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.agents.scrapers.metro_scraper import MetroScraper
from app.agents.scrapers.walmart_scraper import WalmartScraper
from app.agents.scrapers.maxi_scraper import MaxiScraper
from app.agents.scrapers.provigo_scraper import ProvigoScraper
from app.agents.scrapers.iga_scraper import IgaScraper
from app.agents.scrapers.super_c_scraper import SuperCScraper
from app.agents.scrapers.adonis_scraper import AdonisScraper
from app.agents.scrapers.costco_scraper import CostcoScraper
from app.services.notification_service import NotificationService
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("scraper_validation")

async def validate_scraper(name: str, scraper_factory: Any) -> Dict[str, Any]:
    """
    Validates a single scraper by attempting to scrape 1 deal.
    """
    logger.info(f"Validating {name} scraper...")
    try:
        # Use a timeout to prevent hanging
        scraper = scraper_factory()
        deals = await asyncio.wait_for(scraper.scrape(limit=1), timeout=120)

        if deals and len(deals) > 0:
            logger.info(f"✅ {name} scraper validation PASSED.")
            return {"success": True, "error": None}
        else:
            logger.error(f"❌ {name} scraper validation FAILED: No deals found.")
            return {"success": False, "error": "No deals found"}
    except asyncio.TimeoutError:
        logger.error(f"❌ {name} scraper validation FAILED: Timeout.")
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        logger.error(f"❌ {name} scraper validation FAILED: {str(e)}")
        return {"success": False, "error": str(e)}

async def main():
    scrapers_to_validate = {
        "Metro": lambda: MetroScraper(headless=True),
        "Walmart": lambda: WalmartScraper(headless=True),
        "Maxi": lambda: MaxiScraper(headless=True),
        "Provigo": lambda: ProvigoScraper(headless=True),
        "IGA": lambda: IgaScraper(headless=True),
        "Super C": lambda: SuperCScraper(headless=True),
        "Adonis": lambda: AdonisScraper(postal_code=settings.DEFAULT_POSTAL_CODE),
        "Costco": lambda: CostcoScraper(headless=True),
    }

    results = {}
    for name, scraper_factory in scrapers_to_validate.items():
        results[name] = await validate_scraper(name, scraper_factory)

    # Send summary notification
    await NotificationService.send_validation_summary(results)

    # Exit with error code if any failed
    if any(not res["success"] for res in results.values()):
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
