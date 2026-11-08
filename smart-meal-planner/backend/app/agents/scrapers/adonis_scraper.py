from app.core.config import settings
import logging
from typing import List, Dict, Any, Optional
from app.agents.flipp_scraper import FlippScraper

logger = logging.getLogger(__name__)

class AdonisScraper(FlippScraper):
    """
    Scraper for Adonis grocery stores.
    This scraper leverages the Flipp API, as Adonis flyers are available on Flipp.
    """
    def __init__(self, postal_code: Optional[str] = None, headless: bool = True, proxy_manager: Optional[Any] = None, storage_path: str = "/tmp"):
        postal_code = postal_code or getattr(settings, "LOCAL_POSTAL_CODE", None) or settings.DEFAULT_POSTAL_CODE
        super().__init__(postal_code=postal_code, stores=["adonis"])

    async def scrape(self, limit: int = 50, search_terms: Optional[List[str]] = None) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Scrapes Adonis deals using the Flipp API.
        """
        logger.info("Scraping Adonis via Flipp API...")
        deals = await super().scrape(limit=limit, search_terms=search_terms)
        return deals, None
