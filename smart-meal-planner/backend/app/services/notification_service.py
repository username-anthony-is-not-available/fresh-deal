import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Service for sending notifications to external systems like Slack or Telegram.
    Uses a webhook URL for delivery.
    """

    @staticmethod
    async def send_notification(message: str):
        """
        Sends a notification to the configured webhook URL.
        The message is sent as a JSON object with a "text" key,
        which is compatible with Slack and many other systems.
        """
        if not settings.WEBHOOK_URL:
            logger.warning("No WEBHOOK_URL configured. Notification skipped.")
            return

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.WEBHOOK_URL,
                    json={"text": message},
                    timeout=10.0
                )
                response.raise_for_status()
                logger.info("Notification sent successfully.")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}", exc_info=True)

    @staticmethod
    async def send_scraper_failure_alert(store_name: str, error: str):
        """
        Sends a specific alert for a scraper failure.
        """
        message = f"🚨 *Scraper Failure Alert*\n*Store:* {store_name}\n*Error:* {error}\n*Action:* Investigation required."
        await NotificationService.send_notification(message)

    @staticmethod
    async def send_validation_summary(results: dict):
        """
        Sends a summary of scraper validation results.
        results: dict mapping store names to success/failure info
        """
        failures = [store for store, res in results.items() if not res['success']]

        if not failures:
            message = "✅ *Scraper Validation Passed*\nAll scrapers are working correctly."
        else:
            failure_details = "\n".join([f"• {store}: {results[store]['error']}" for store in failures])
            message = f"❌ *Scraper Validation Failed*\nThe following scrapers failed:\n{failure_details}"

        await NotificationService.send_notification(message)
