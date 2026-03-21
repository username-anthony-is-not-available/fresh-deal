import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.models.all_models import Store, User
from app.tasks import generate_meal_plan_task
from app.agents.scraper_agent import ScraperAgent
from unittest.mock import patch, MagicMock

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

@patch("app.tasks.Session")
@patch("app.tasks.scrape_task.delay")
@patch("app.tasks.MealPlannerAgent")
@patch("app.tasks.PantryService")
def test_generate_meal_plan_task_triggers_scrape_on_stale_deals(
    mock_pantry, mock_planner, mock_scrape_delay, mock_session_class
):
    """
    Verifies that generate_meal_plan_task correctly identifies stale stores
    and triggers a background scrape.
    """
    # Arrange
    mock_session = MagicMock(spec=Session)
    mock_session_class.return_value.__enter__.return_value = mock_session

    # Create a stale store
    stale_store = Store(name="Stale Store", chain="stale_chain", postal_code="H4T1V6")
    stale_store.last_scraped_at = datetime.now(timezone.utc) - timedelta(days=10)

    # Create a fresh store
    fresh_store = Store(name="Fresh Store", chain="fresh_chain", postal_code="H4T1V6")
    fresh_store.last_scraped_at = datetime.now(timezone.utc) - timedelta(days=1)

    mock_session.exec.return_value.all.return_value = [stale_store, fresh_store]
    # Handle active deals count check
    mock_session.exec.return_value.one.return_value = 100

    mock_user = User(id=1, email="test@example.com", household_size=2, postal_code="H4T1V6")
    mock_session.get.return_value = mock_user

    mock_planner.return_value.generate_plan.return_value = {
        "meal_plan": [{"date": "2024-01-01"}],
        "shopping_summary": {}
    }

    # Act
    generate_meal_plan_task(1)

    # Assert
    mock_scrape_delay.assert_called_once_with(stores=["stale_chain"], postal_code="H4T1V6")

@pytest.mark.asyncio
async def test_mark_store_as_scraped(async_session):
    """
    Verifies that mark_store_as_scraped updates the last_scraped_at field.
    """
    # Arrange
    store = Store(name="Test Store", chain="test_chain", postal_code="H4T1V6")
    async_session.add(store)
    await async_session.commit()

    agent = ScraperAgent(async_session)

    # Act
    await agent.mark_store_as_scraped("test_chain")

    # Assert
    await async_session.refresh(store)
    assert store.last_scraped_at is not None
    # Handle possible naive/aware mismatch from SQLite
    last_scraped = store.last_scraped_at
    if last_scraped.tzinfo is not None:
        diff = datetime.now(timezone.utc) - last_scraped
    else:
        diff = datetime.now() - last_scraped
    assert diff.total_seconds() < 60
