import pytest
from unittest.mock import patch, AsyncMock
from app.agents.scraper_agent import ScraperAgent
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

@pytest.mark.asyncio
async def test_scraper_agent_notifies_on_direct_failure():
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)
    agent = ScraperAgent(mock_session)

    # Mock the direct scraper to fail
    # We need to mock the scrape method of the specific scraper class
    # Since ScraperAgent instantiates them in __init__

    with patch('app.agents.scrapers.walmart_scraper.WalmartScraper.scrape', new_callable=AsyncMock) as mock_scrape:
        mock_scrape.side_effect = Exception("Structure changed")

        # Mock fallbacks to succeed so the whole process doesn't fail
        with patch.object(agent, '_scrape_with_flipp', new_callable=AsyncMock) as mock_flipp:
            mock_flipp.return_value = [{"name": "Fallback Product", "price": 1.0, "store": "Walmart"}]

            # Mock notification service
            with patch('app.services.notification_service.NotificationService.send_scraper_failure_alert', new_callable=AsyncMock) as mock_alert:

                # We need to reduce retries and sleep time for faster test
                with patch('asyncio.sleep', new_callable=AsyncMock):
                    # Act
                    deals = await agent._scrape_store("walmart", limit=1)

                    # Assert
                    assert len(deals) == 1
                    assert deals[0]["name"] == "Fallback Product"

                    # Check that alert was sent
                    mock_alert.assert_called_once()
                    args = mock_alert.call_args[0]
                    assert args[0] == "walmart"
                    assert "Structure changed" in args[1]
