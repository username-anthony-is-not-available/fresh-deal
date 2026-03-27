
import pytest
from httpx import AsyncClient, ASGITransport
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel.pool import StaticPool
from app.main import app
from app.core.db import get_async_session
from app.models.all_models import Store, Product, Deal
from datetime import date, timedelta
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


@pytest_asyncio.fixture(name="client", scope="function")
async def client_fixture(session: AsyncSession):
    def get_session_override():
        return session

    app.dependency_overrides[get_async_session] = get_session_override

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_list_deals_proximity_filtering(client: AsyncClient, session: AsyncSession):
    # Setup mock stores
    s1 = Store(name="Close Store", chain="Walmart", postal_code="H4T1V6") # 0km from H4T
    s2 = Store(name="Far Store", chain="Maxi", postal_code="H1A1A1") # ~20km from H4T
    session.add(s1)
    session.add(s2)
    await session.commit()
    await session.refresh(s1)
    await session.refresh(s2)

    # Setup mock product
    p1 = Product(name="Milk", category="Dairy", unit_type="L")
    session.add(p1)
    await session.commit()
    await session.refresh(p1)

    # Setup mock deals
    d1 = Deal(product_id=p1.id, store_id=s1.id, price=2.0, valid_from=date.today(), valid_until=date.today()+timedelta(7))
    d2 = Deal(product_id=p1.id, store_id=s2.id, price=1.5, valid_from=date.today(), valid_until=date.today()+timedelta(7))
    session.add(d1)
    session.add(d2)
    await session.commit()

    # Request deals with postal code
    response = await client.get("/api/deals", params={"postal_code": "H4T1V6"})
    assert response.status_code == 200
    data = response.json()

    # Should only contain "Close Store" deal
    assert len(data) == 1
    assert data[0]["store"]["name"] == "Close Store"
    assert data[0]["distance"] == 0.0

@pytest.mark.asyncio
async def test_list_deals_sorting_distance(client: AsyncClient, session: AsyncSession):
    # H4T: (45.4954, -73.6798)
    # H4E: (45.4542, -73.5855) ~8.7km
    # H4B: (45.4600, -73.6300) ~5.5km

    s1 = Store(name="H4E Store", chain="C1", postal_code="H4E1A1")
    s2 = Store(name="H4B Store", chain="C2", postal_code="H4B1W3")

    session.add(s1)
    session.add(s2)
    await session.commit()
    await session.refresh(s1)
    await session.refresh(s2)

    p1 = Product(name="Bread", category="Bakery", unit_type="Loaf")
    session.add(p1)
    await session.commit()
    await session.refresh(p1)

    d1 = Deal(product_id=p1.id, store_id=s1.id, price=2.0, valid_from=date.today(), valid_until=date.today()+timedelta(7))
    d2 = Deal(product_id=p1.id, store_id=s2.id, price=1.5, valid_from=date.today(), valid_until=date.today()+timedelta(7))
    session.add(d1)
    session.add(d2)
    await session.commit()

    # Request deals with sort_by=distance.
    # Since they are both > 5km from H4T, they would be filtered out if I provide postal_code=H4T.
    # So I'll use a postal code that is closer to one but still includes both, or just test sorting.
    # Wait, the 5km limit is ALWAYS applied if postal_code is provided.

    # Let's use H4B as my postal code.
    # Distance to H4B Store (H4B1W3) is 0km.
    # Distance to H4E Store (H4E1A1) is ~4.4km.
    # Both are < 5km from H4B.

    response = await client.get("/api/deals", params={"postal_code": "H4B1W3", "sort_by": "distance"})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    assert data[0]["store"]["name"] == "H4B Store"
    assert data[1]["store"]["name"] == "H4E Store"
    assert data[0]["distance"] < data[1]["distance"]
