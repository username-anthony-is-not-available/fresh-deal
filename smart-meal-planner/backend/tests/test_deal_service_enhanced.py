import pytest
from datetime import date, timedelta
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel.pool import StaticPool
from app.models.all_models import Deal, Product, Store
from app.services.deal_service import DealService
import pytest_asyncio

# Use aiosqlite for async testing
DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@pytest_asyncio.fixture(name="session", scope="function")
async def session_fixture():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

@pytest.mark.asyncio
async def test_get_top_deals(session: AsyncSession):
    # Setup test data
    store = Store(name="Test Store", chain="test", postal_code="H4T1V6")
    session.add(store)
    await session.commit()
    await session.refresh(store)

    product1 = Product(name="Chicken", category="Meat", unit_type="kg")
    product2 = Product(name="Apple", category="Produce", unit_type="lb")
    session.add(product1)
    session.add(product2)
    await session.commit()
    await session.refresh(product1)
    await session.refresh(product2)

    today = date.today()
    deal1 = Deal(
        product_id=product1.id,
        store_id=store.id,
        price=5.0,
        original_price=10.0,
        discount_pct=50.0,
        valid_from=today,
        valid_until=today + timedelta(days=7)
    )
    deal2 = Deal(
        product_id=product2.id,
        store_id=store.id,
        price=1.0,
        original_price=1.2,
        discount_pct=16.6,
        valid_from=today,
        valid_until=today + timedelta(days=7)
    )
    session.add(deal1)
    session.add(deal2)
    await session.commit()

    service = DealService(session)

    # Test without postal code
    top_deals = await service.get_top_deals(limit=10)
    assert len(top_deals) == 2
    assert top_deals[0]["product"] == "Chicken"  # Should be ranked higher due to 50% discount

    # Test with matching postal code
    top_deals_fsa = await service.get_top_deals(limit=10, postal_code="H4T 2A1")
    assert len(top_deals_fsa) == 2

    # Test with non-matching postal code
    top_deals_none = await service.get_top_deals(limit=10, postal_code="M5V 1J2")
    assert len(top_deals_none) == 0
