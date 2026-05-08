import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlmodel import SQLModel, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.models.all_models import ScraperLog
from app.services.scraper_health_service import ScraperHealthService

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

@pytest.mark.asyncio
async def test_reset_store_circuit_breaker(async_session):
    """
    Verifies that reset_store_circuit_breaker deletes recent failure logs.
    """
    # Arrange
    store_name = "test_store"
    now = datetime.now(timezone.utc)

    # 1. Add recent failures
    async_session.add(ScraperLog(store_name=store_name, status="failure", timestamp=now - timedelta(hours=2)))
    async_session.add(ScraperLog(store_name=store_name, status="failure", timestamp=now - timedelta(hours=1)))

    # 2. Add old failure (should NOT be deleted based on current impl, but the impl says >= 24h)
    # Actually, the impl says:
    # since_date = datetime.now(timezone.utc) - timedelta(hours=24)
    # stmt = delete(ScraperLog).where(..., ScraperLog.timestamp >= since_date)
    # So it deletes failures from the last 24h.
    async_session.add(ScraperLog(store_name=store_name, status="failure", timestamp=now - timedelta(hours=48)))

    # 3. Add recent success (should NOT be deleted)
    async_session.add(ScraperLog(store_name=store_name, status="success", timestamp=now - timedelta(hours=1)))

    await async_session.commit()

    health_service = ScraperHealthService(async_session)

    # Act
    await health_service.reset_store_circuit_breaker(store_name)

    # Assert
    stmt = select(ScraperLog).where(ScraperLog.store_name == store_name)
    result = await async_session.execute(stmt)
    logs = result.scalars().all()

    # Should have 2 logs left: 1 old failure and 1 recent success
    assert len(logs) == 2
    statuses = [log.status for log in logs]
    assert "success" in statuses
    assert "failure" in statuses
    for log in logs:
        if log.status == "failure":
            # SQLite might return naive datetimes, but we'll try to check the age
            # If it's aware:
            if log.timestamp.tzinfo:
                assert log.timestamp < now - timedelta(hours=24)

@pytest.mark.asyncio
async def test_refined_error_categorization(async_session):
    """
    Verifies that get_store_health_metrics correctly categorizes new error tags.
    """
    # Arrange
    store_name = "error_store"
    now = datetime.now(timezone.utc)
    # Failures must be more recent than success to be counted in the streak
    async_session.add(ScraperLog(store_name=store_name, status="success", items_scraped=10, timestamp=now - timedelta(minutes=10)))
    async_session.add(ScraperLog(store_name=store_name, status="failure", error_message="[PROXY_FAIL] Connection timed out", timestamp=now - timedelta(minutes=5)))
    async_session.add(ScraperLog(store_name=store_name, status="failure", error_message="[RATE_LIMIT] Too many requests", timestamp=now - timedelta(minutes=1)))
    await async_session.commit()

    health_service = ScraperHealthService(async_session)

    # Act
    metrics = await health_service.get_store_health_metrics(days=1)

    # Assert
    store_metric = next(m for m in metrics if m["store_name"] == store_name)
    breakdown = store_metric["error_breakdown"]

    assert breakdown.get("Proxy Failure") == 1
    assert breakdown.get("Rate Limited") == 1
    # Total items should be 10
    assert store_metric["total_items_scraped"] == 10
