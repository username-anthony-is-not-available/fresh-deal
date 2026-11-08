"""
RETIRED / DEPRECATED: ScraperBridgeService
Consolidated into backend app.agents.scrapers. This file is retained solely as a
lightweight compatibility layer for any legacy callers and tests.
"""

import logging
from typing import List, Dict, Any, Optional
from app.agents.scrapers.base_scraper import BaseScraper
from app.agents.scrapers.provigo_scraper import ProvigoScraper
from app.agents.scrapers.metro_scraper import MetroScraper
from app.agents.scrapers.super_c_scraper import SuperCScraper

logger = logging.getLogger(__name__)

class ScraperBridgeService:
    """
    Deprecated bridge service. Scrapers are now unified directly inside
    smart-meal-planner/backend/app/agents/scrapers/.
    """

    SCRAPER_MAP = {
        "provigo": ProvigoScraper,
        "metro": MetroScraper,
        "super_c": SuperCScraper,
    }

    @staticmethod
    async def run_root_scraper(
        store_name: str, postal_code: str = "H4T1V6", limit: int = 50, headless: bool = True
    ) -> List[Dict[str, Any]]:
        scraper_class = ScraperBridgeService.SCRAPER_MAP.get(store_name.lower())
        if not scraper_class:
            logger.warning(f"No unified scraper found for store: {store_name}")
            return []

        logger.info(f"Running unified scraper for {store_name} (Postal Code: {postal_code})")
        scraper = scraper_class(postal_code=postal_code, headless=headless)

        try:
            deals, _, _, _ = await scraper.scrape(limit=limit)
            return [ScraperBridgeService._map_deal_to_dict(d) for d in deals]
        except Exception as e:
            logger.error(f"Unified scraper for {store_name} failed: {e}")
            return []

    @staticmethod
    def _map_deal_to_dict(deal: Any) -> Dict[str, Any]:
        if isinstance(deal, dict):
            return deal
        return {
            "name": getattr(deal, "name", ""),
            "price": getattr(deal, "price", 0.0),
            "original_price": getattr(deal, "original_price", getattr(deal, "price", 0.0)),
            "unit": getattr(deal, "unit", "each"),
            "category": getattr(deal, "category", "Grocery"),
            "store": getattr(deal, "store", ""),
            "valid_from": getattr(deal, "valid_from", None),
            "valid_until": getattr(deal, "valid_until", None),
            "loyalty_program": getattr(deal, "loyalty_program", None),
            "loyalty_points": getattr(deal, "loyalty_points", None),
            "image_url": getattr(deal, "image_url", None),
            "sale_info": getattr(deal, "sale_info", None),
        }
