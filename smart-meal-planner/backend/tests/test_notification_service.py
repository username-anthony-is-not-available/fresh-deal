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
