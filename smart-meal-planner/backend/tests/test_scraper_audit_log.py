import pytest
import pytest_asyncio
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlmodel import SQLModel
from app.models.all_models import ScraperLog, User
from app.agents.scraper_agent import ScraperAgent
from app.agents.scrapers.base_scraper import BaseScraper
from playwright.async_api import Page

# Setup for async tests
async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")

async def setup_async_database():
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

async def teardown_async_database():
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

@pytest_asyncio.fixture
async def async_session():
    await setup_async_database()
    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        yield session
    await teardown_async_database()

class MockDirectScraper(BaseScraper):
    async def _scrape_page(self, page: Page, limit: int):
        return [{"name": "Mock Deal", "price": 1.99, "store": "MockStore"}]

@pytest.mark.asyncio
async def test_scraper_log_success_no_artifacts(async_session):
    """Verifies that a successful scrape logs without artifacts."""
    # Arrange
    store_name = "metro"
    agent = ScraperAgent(async_session)
    mock_scraper = MockDirectScraper()

    # Mock the scrape method to return success
    mock_scraper.scrape = AsyncMock(return_value=([{"name": "Deal", "price": 1.0, "store": "Metro"}], "1.2.3.4:8080", None, None))
    agent.scrapers[store_name] = mock_scraper

    # Act
    await agent.scrape(stores=[store_name])

    # Assert
    stmt = select(ScraperLog).where(ScraperLog.store_name == store_name)
    result = await async_session.execute(stmt)
    log = result.scalars().first()

    assert log.status == "success"
    assert log.screenshot_path is None
    assert log.html_path is None
    assert log.items_scraped == 1

@pytest.mark.asyncio
async def test_scraper_log_failure_with_artifacts(async_session):
    """Verifies that a failed scrape captures and logs artifacts."""
    # Arrange
    store_name = "walmart"
    agent = ScraperAgent(async_session)
    mock_scraper = MockDirectScraper()

    # Mock save_debug_artifacts to return fake paths
    fake_screenshot = "/tmp/failure.png"
    fake_html = "/tmp/failure.html"

    # We need to simulate the failure inside scrape() and ensure artifacts are set on the scraper object
    async def side_effect(*args, **kwargs):
        mock_scraper.last_screenshot = fake_screenshot
        mock_scraper.last_html = fake_html
        raise Exception("Simulated Scraping Failure")

    mock_scraper.scrape = AsyncMock(side_effect=side_effect)
    agent.scrapers[store_name] = mock_scraper

    # Act
    # Mock fallback scrapers to also return nothing, so the overall status is failure
    with patch.object(ScraperAgent, '_scrape_with_flipp', return_value=[]), \
         patch.object(ScraperAgent, '_scrape_with_circulaire_en_ligne', return_value=[]):
        await agent.scrape(stores=[store_name])

    # Assert
    stmt = select(ScraperLog).where(ScraperLog.store_name == store_name)
    result = await async_session.execute(stmt)
    logs = result.scalars().all()

    # In the current implementation, ScraperAgent might log multiple attempts or just one final log.
    # Looking at _log_scrape call in ScraperAgent.scrape, it's called once after all retries and fallbacks.
    assert len(logs) == 1
    log = logs[0]

    assert log.status == "failure"
    assert log.screenshot_path == fake_screenshot
    assert log.html_path == fake_html
    assert "Simulated Scraping Failure" in log.error_message

@pytest.mark.asyncio
async def test_api_get_logs(async_session):
    """Verifies the GET /admin/scrapers/logs endpoint."""
    from app.api.endpoints import get_scraper_logs

    # Arrange
    async_session.add(ScraperLog(store_name="Store1", status="success", timestamp=datetime.now(timezone.utc)))
    async_session.add(ScraperLog(store_name="Store2", status="failure", screenshot_path="s.png", timestamp=datetime.now(timezone.utc)))
    await async_session.commit()

    # Act
    logs = await get_scraper_logs(session=async_session, current_user=User(id=1, email="a@b.com"))

    # Assert
    assert len(logs) == 2
    # Ordered by timestamp desc
    assert logs[0].store_name == "Store2"
    assert logs[0].screenshot_path == "s.png"
    assert logs[1].store_name == "Store1"

    # Test filtering
    filtered_logs = await get_scraper_logs(status="failure", session=async_session, current_user=User(id=1, email="a@b.com"))
    assert len(filtered_logs) == 1
    assert filtered_logs[0].store_name == "Store2"

@pytest.mark.asyncio
async def test_api_get_log_artifacts(async_session):
    """Verifies the GET /admin/scrapers/logs/{log_id}/screenshot and html endpoints."""
    from app.api.endpoints import get_scraper_log_screenshot, get_scraper_log_html

    # Create dummy files within allowed directory
    os.makedirs("/tmp/scrapers", exist_ok=True)
    screenshot_path = "/tmp/scrapers/test_s.png"
    html_path = "/tmp/scrapers/test_h.html"
    with open(screenshot_path, "wb") as f: f.write(b"fake image")
    with open(html_path, "w") as f: f.write("<html></html>")

    try:
        # Arrange
        log = ScraperLog(
            store_name="Store1",
            status="failure",
            screenshot_path=screenshot_path,
            html_path=html_path,
            timestamp=datetime.now(timezone.utc)
        )
        async_session.add(log)
        await async_session.commit()
        await async_session.refresh(log)

        # Act
        screenshot_response = await get_scraper_log_screenshot(log_id=log.id, session=async_session, current_user=User(id=1, email="a@b.com"))
        html_response = await get_scraper_log_html(log_id=log.id, session=async_session, current_user=User(id=1, email="a@b.com"))

        # Assert
        assert screenshot_response.path == screenshot_path
        assert screenshot_response.media_type == "image/png"
        assert html_response.path == html_path
        assert html_response.media_type == "text/html"
    finally:
        # Cleanup
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)
        if os.path.exists(html_path):
            os.remove(html_path)
