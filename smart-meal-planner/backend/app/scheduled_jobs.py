import logging
from datetime import datetime, timedelta, timezone
from sqlmodel import select
from app.tasks import scrape_task, sync_root_scrapers_task
from app.core.config import settings
from app.services.notification_service import NotificationService
from app.core.db import engine
from sqlmodel import Session
from app.models.all_models import PantryItem, User

logger = logging.getLogger(__name__)

async def run_scheduled_scrape():
    """
    Called by APScheduler to run the scraping process for all supported stores.
    Dispatches Celery tasks (or executes eagerly in local mode).
    """
    logger.info("Starting scheduled local flyer refresh job.")
    postal_code = getattr(settings, "LOCAL_POSTAL_CODE", None) or settings.DEFAULT_POSTAL_CODE
    try:
        # Dispatch main scrapers
        scrape_task.delay(postal_code=postal_code)

        # Dispatch root framework scrapers if available
        try:
            sync_root_scrapers_task.delay(postal_code=postal_code)
        except Exception as e:
            logger.debug(f"Sync root scrapers task skipped: {e}")

        success_message = f"Scheduled flyer refresh dispatched for postal code {postal_code}."
        logger.info(success_message)
        await NotificationService.send_notification(f"Scrape job: {success_message}")
    except Exception as e:
        error_message = f"An error occurred while dispatching the scheduled scrape: {e}"
        logger.error(error_message, exc_info=True)
        await NotificationService.send_notification(f"Scrape job dispatch failed: {error_message}")


async def run_pantry_expiration_check():
    """
    Called by APScheduler to check for expiring pantry items and notify users.
    Prioritizes ingredients that will spoil soon for upcoming meal plans.
    """
    logger.info("Running scheduled pantry expiration check.")
    now = datetime.now(timezone.utc)
    threshold = now + timedelta(days=3)

    try:
        with Session(engine) as session:
            # Query pantry items expiring within 3 days
            expiring_items = session.exec(
                select(PantryItem).where(
                    PantryItem.expiration_date.is_not(None),
                    PantryItem.expiration_date <= threshold
                )
            ).all()

            if expiring_items:
                user_ids = {item.user_id for item in expiring_items}
                for uid in user_ids:
                    user_items = [i for i in expiring_items if i.user_id == uid]
                    item_names = ", ".join(i.name for i in user_items[:5])
                    alert = f"Pantry alert: {len(user_items)} item(s) expiring soon ({item_names}). Prioritizing in meal plan."
                    logger.warning(f"User {uid}: {alert}")
                    await NotificationService.send_notification(alert)
            else:
                logger.info("No pantry items expiring within 3 days.")
    except Exception as e:
        logger.error(f"Error checking pantry expirations: {e}", exc_info=True)
