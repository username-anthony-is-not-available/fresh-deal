import asyncio
import httpx
from sqlmodel import select
from app.core.db import get_async_session
from app.agents.scraper_agent import ScraperAgent
from app.models.all_models import Store
import logging
from datetime import datetime, timezone
from app.core.config import settings

logger = logging.getLogger(__name__)

async def send_webhook_notification(message: str):
    """
    Sends a notification to the configured webhook URL.
    """
    if settings.WEBHOOK_URL:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(settings.WEBHOOK_URL, json={"text": message})
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}", exc_info=True)

async def run_scheduled_scrape():
    """
    Called by the scheduler to run the scraping process for all supported stores.
    """
    logger.info("Starting scheduled scrape job.")
    try:
        async with get_async_session() as session:
            statement = select(Store).where(Store.chain.in_(settings.SUPPORTED_STORES))
            result = await session.execute(statement)
            stores_to_scrape = result.scalars().all()

            if not stores_to_scrape:
                logger.warning("No supported stores found in the database to scrape.")
                await send_webhook_notification("Scrape job finished: No supported stores found.")
                return

            store_map = {store.chain: store for store in stores_to_scrape}
            store_chains = list(store_map.keys())

            scraper_agent = ScraperAgent(session, settings.DEFAULT_POSTAL_CODE)
            deals_by_store = await scraper_agent.scrape(store_chains)

            total_deals = 0
            for store_chain, deals in deals_by_store.items():
                if deals:
                    await scraper_agent.persist_deals(deals)
                    store = store_map.get(store_chain)
                    if store:
                        store.last_scraped_at = datetime.now(timezone.utc)
                        session.add(store)
                    total_deals += len(deals)

            if total_deals > 0:
                await session.commit()
                success_message = f"Successfully scraped and persisted {total_deals} deals."
                logger.info(success_message)
                await send_webhook_notification(f"Scrape job finished: {success_message}")
            else:
                logger.info("No new deals found during scheduled scrape.")
                await send_webhook_notification("Scrape job finished: No new deals found.")

    except Exception as e:
        error_message = f"An error occurred during the scheduled scrape: {e}"
        logger.error(error_message, exc_info=True)
        await send_webhook_notification(f"Scrape job failed: {error_message}")
