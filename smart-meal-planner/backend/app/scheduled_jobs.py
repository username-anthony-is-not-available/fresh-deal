import asyncio
import httpx
from sqlmodel import select
from app.core.db import get_async_session
from app.agents.scraper_agent import ScraperAgent
from app.models.all_models import Store
import logging
from datetime import datetime, timezone
from app.core.config import settings
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

async def run_scheduled_scrape():
    """
    Called by the scheduler to run the scraping process for all supported stores.
    Uses the ScraperAgent to orchestrate the process and handle persistence.
    """
    logger.info("Starting scheduled scrape job.")
    try:
        async with get_async_session() as session:
            scraper_agent = ScraperAgent(session, settings.DEFAULT_POSTAL_CODE)
            await scraper_agent.run_daily_scrape()

            success_message = "Scheduled scrape job finished successfully."
            logger.info(success_message)
            await NotificationService.send_notification(f"Scrape job finished: {success_message}")

    except Exception as e:
        error_message = f"An error occurred during the scheduled scrape: {e}"
        logger.error(error_message, exc_info=True)
        await NotificationService.send_notification(f"Scrape job failed: {error_message}")
