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
            # We scrape all supported stores regardless of whether they are already in the DB
            store_chains = settings.SUPPORTED_STORES

            # Fetch existing stores for later updating last_scraped_at
            statement = select(Store).where(Store.chain.in_(store_chains))
            result = await session.execute(statement)
            existing_stores = result.scalars().all()
            store_map = {store.chain: store for store in existing_stores}

            scraper_agent = ScraperAgent(session, settings.DEFAULT_POSTAL_CODE)
            deals_by_store = await scraper_agent.scrape(store_chains)

            total_deals = 0
            for store_chain, deals in deals_by_store.items():
                if deals:
                    # Persist deals will also create the store in DB if it doesn't exist
                    await scraper_agent.persist_deals(deals)

                    # Refresh store map to get newly created stores
                    statement = select(Store).where(Store.chain == store_chain)
                    result = await session.execute(statement)
                    store = result.scalar_one_or_none()

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
