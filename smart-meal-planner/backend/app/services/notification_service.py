import httpx
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any
from app.core.config import settings
from app.models.all_models import User

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

    @staticmethod
    def send_email(to_email: str, subject: str, html_content: str):
        """
        Sends an email using the configured SMTP settings.
        """
        if not settings.EMAILS_ENABLED:
            logger.warning("Email notifications are disabled.")
            return

        if not settings.SMTP_HOST:
            logger.warning("No SMTP_HOST configured. Email skipped.")
            return

        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
            message["To"] = to_email

            part = MIMEText(html_content, "html")
            message.attach(part)

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.starttls()
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.EMAILS_FROM_EMAIL, to_email, message.as_string())

            logger.info(f"Email sent successfully to {to_email}.")
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}", exc_info=True)

    @staticmethod
    def generate_deals_digest_html(deals: List[Dict[str, Any]]) -> str:
        """
        Generates a clean HTML template for the grocery deals digest.
        """
        items_html = ""
        for deal in deals:
            price_display = f"${deal['price']:.2f}"
            if deal.get('unit'):
                price_display += f"/{deal['unit']}"

            discount_info = ""
            if deal.get('discount_pct'):
                discount_info = f"<span style='color: #d32f2f; font-weight: bold;'>({int(deal['discount_pct'])}% OFF)</span>"
            elif deal.get('original_price'):
                discount_info = f"<span style='color: #d32f2f; font-weight: bold;'>Save ${deal['original_price'] - deal['price']:.2f}</span>"

            items_html += f"""
            <div style="border-bottom: 1px solid #eee; padding: 15px 0;">
                <h3 style="margin: 0 0 5px 0; color: #333;">{deal['product']}</h3>
                <p style="margin: 0; color: #666;">
                    <strong style="font-size: 1.2em; color: #2e7d32;">{price_display}</strong> {discount_info}
                </p>
                <p style="margin: 5px 0 0 0; font-size: 0.9em; color: #888;">
                    Store: <strong>{deal['store']}</strong> | Category: {deal['category']}
                </p>
            </div>
            """

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #2e7d32; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                <h1 style="margin: 0;">Top Grocery Deals</h1>
                <p style="margin: 5px 0 0 0;">Your daily digest from Smart Meal Planner</p>
            </div>
            <div style="background-color: #fff; padding: 20px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 8px 8px;">
                <p>Hi there! Here are the top 10 grocery deals near you today:</p>
                {items_html}
                <div style="margin-top: 30px; text-align: center; font-size: 0.8em; color: #888;">
                    <p>You are receiving this because you opted in for daily deal digests.</p>
                    <p>&copy; 2024 Smart Meal Planner. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html

    @staticmethod
    async def send_daily_deals_digest(user: User, deals: List[Dict[str, Any]]):
        """
        Sends the daily deals digest email to a user.
        """
        if not deals:
            logger.info(f"No deals to send for user {user.email}.")
            return

        subject = "Your Daily Top Grocery Deals 🛒"
        html_content = NotificationService.generate_deals_digest_html(deals)
        NotificationService.send_email(user.email, subject, html_content)
