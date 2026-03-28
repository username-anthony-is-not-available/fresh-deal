from app.tasks import scrape_task, sync_root_scrapers_task
import logging
from app.core.config import settings
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

async def run_scheduled_scrape():
    """
    Called by the scheduler to run the scraping process for all supported stores.
    Dispatches Celery tasks to parallelize the process across workers.
    """
    logger.info("Starting scheduled parallel scrape job.")
    try:
        # Dispatch main scrapers
        scrape_task.delay(postal_code=settings.DEFAULT_POSTAL_CODE)

        # Dispatch root framework scrapers
        sync_root_scrapers_task.delay(postal_code=settings.DEFAULT_POSTAL_CODE)

        success_message = "Scheduled parallel scrape jobs dispatched successfully."
        logger.info(success_message)
        await NotificationService.send_notification(f"Scrape job dispatched: {success_message}")

    except Exception as e:
        error_message = f"An error occurred while dispatching the scheduled scrape: {e}"
        logger.error(error_message, exc_info=True)
        await NotificationService.send_notification(f"Scrape job dispatch failed: {error_message}")
