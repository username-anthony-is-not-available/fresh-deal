import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.notification_service import NotificationService
from app.core.config import settings

@pytest.mark.asyncio
async def test_send_notification_success():
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = MagicMock()

        with patch.object(settings, "WEBHOOK_URL", "http://example.com/webhook"):
            await NotificationService.send_notification("Test message")

            mock_post.assert_called_once_with(
                "http://example.com/webhook",
                json={"text": "Test message"},
                timeout=10.0
            )

@pytest.mark.asyncio
async def test_send_notification_no_url():
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        with patch.object(settings, "WEBHOOK_URL", None):
            await NotificationService.send_notification("Test message")
            mock_post.assert_not_called()

@pytest.mark.asyncio
async def test_send_scraper_failure_alert():
    with patch.object(NotificationService, "send_notification", new_callable=AsyncMock) as mock_send:
        await NotificationService.send_scraper_failure_alert("Walmart", "Website structure changed")

        mock_send.assert_called_once()
        message = mock_send.call_args[0][0]
        assert "Walmart" in message
        assert "Website structure changed" in message
        assert "🚨" in message

@pytest.mark.asyncio
async def test_send_validation_summary_success():
    results = {
        "Metro": {"success": True, "error": None},
        "Walmart": {"success": True, "error": None}
    }
    with patch.object(NotificationService, "send_notification", new_callable=AsyncMock) as mock_send:
        await NotificationService.send_validation_summary(results)

        mock_send.assert_called_once()
        message = mock_send.call_args[0][0]
        assert "✅" in message
        assert "Passed" in message

@pytest.mark.asyncio
async def test_send_validation_summary_failure():
    results = {
        "Metro": {"success": True, "error": None},
        "Walmart": {"success": False, "error": "No deals found"}
    }
    with patch.object(NotificationService, "send_notification", new_callable=AsyncMock) as mock_send:
        await NotificationService.send_validation_summary(results)

        mock_send.assert_called_once()
        message = mock_send.call_args[0][0]
        assert "❌" in message
        assert "Failed" in message
        assert "Walmart" in message
        assert "No deals found" in message

def test_generate_deals_digest_html():
    deals = [
        {
            "product": "Chicken",
            "store": "Metro",
            "category": "Meat",
            "price": 5.0,
            "unit": "kg",
            "discount_pct": 50.0
        }
    ]
    html = NotificationService.generate_deals_digest_html(deals)
    assert "Chicken" in html
    assert "$5.00/kg" in html
    assert "50% OFF" in html
    assert "Metro" in html

@pytest.mark.asyncio
async def test_send_email_success():
    with patch("smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        with patch.object(settings, "EMAILS_ENABLED", True):
            with patch.object(settings, "SMTP_HOST", "localhost"):
                NotificationService.send_email("test@example.com", "Subject", "<h1>Test</h1>")

                mock_server.sendmail.assert_called_once()
                assert mock_server.sendmail.call_args[0][0] == settings.EMAILS_FROM_EMAIL
                assert mock_server.sendmail.call_args[0][1] == "test@example.com"
