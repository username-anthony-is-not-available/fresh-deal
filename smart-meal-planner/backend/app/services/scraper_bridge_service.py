import sys
import os
import logging
from typing import List, Dict, Any

# Add the project root to sys.path to allow importing from the root 'src' directory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from src.scrapers.provigo_scraper import ProvigoScraper
    # Import other scrapers as they are added to the root framework
    # from src.scrapers.walmart_scraper import WalmartScraper
except ImportError as e:
    logging.error(f"Failed to import root scrapers: {e}")
    ProvigoScraper = None

class ScraperBridgeService:
    """
    Bridge service to run scrapers from the root-level framework
    and convert their output to the backend's expected format.
    """

    SCRAPER_MAP = {
        "provigo": ProvigoScraper,
        # Add more mappings as root scrapers are implemented
    }

    @staticmethod
    async def run_root_scraper(store_name: str, postal_code: str = "H4T1V6", limit: int = 50, headless: bool = True) -> List[Dict[str, Any]]:
        """
        Runs a specific scraper from the root framework.
        """
        scraper_class = ScraperBridgeService.SCRAPER_MAP.get(store_name.lower())
        if not scraper_class:
            logging.warning(f"No root scraper found for store: {store_name}")
            return []

        logging.info(f"Running root scraper for {store_name} (Postal Code: {postal_code})")
        scraper = scraper_class(postal_code=postal_code, headless=headless)

        try:
            deals = await scraper.scrape(limit=limit)
            return [ScraperBridgeService._map_deal_to_dict(d) for d in deals]
        except Exception as e:
            logging.error(f"Root scraper for {store_name} failed: {e}")
            return []

    @staticmethod
    def _map_deal_to_dict(deal: Any) -> Dict[str, Any]:
        """
        Converts a root-level Deal object (Pydantic) to the backend's dictionary format.
        """
        # deal is an instance of src.core.schema_validator.Deal
        return {
            "name": deal.name,
            "price": deal.price,
            "original_price": deal.original_price or deal.price,
            "unit": deal.unit,
            "store": deal.store,
            "category": deal.category,
            "image_url": deal.image_url,
            "valid_from": deal.valid_from,
            "valid_until": deal.valid_until,
            "loyalty_program": deal.loyalty_program,
            "loyalty_points": deal.loyalty_points,
            "sale_info": deal.sale_info
        }
