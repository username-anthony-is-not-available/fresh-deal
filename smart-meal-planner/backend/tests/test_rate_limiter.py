import pytest
from httpx import AsyncClient
from app.main import app
import pytest_asyncio
from httpx import ASGITransport
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel.pool import StaticPool
from app.core.db import get_async_session
from app.core.security import create_access_token

# Use aiosqlite for async testing
DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

@pytest_asyncio.fixture(name="session", scope="function")
async def session_fixture():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
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
async def test_rate_limit_health_check(client: AsyncClient):
    # The health check endpoint is covered by the default limit of 60/minute.
    # We'll make 61 requests to ensure we trigger the rate limit.
    for i in range(61):
        response = await client.get("/health")
        if response.status_code == 429:
            break
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert "Rate limit exceeded" in response.json()["detail"]


@pytest.mark.asyncio
async def test_rate_limit_authenticated_user(client: AsyncClient):
    # Create two users and generate access tokens for them
    user1_token = create_access_token(subject=1)
    user2_token = create_access_token(subject=2)

    headers1 = {"Authorization": f"Bearer {user1_token}"}
    headers2 = {"Authorization": f"Bearer {user2_token}"}

    # Exhaust the rate limit for user1
    for i in range(61):
        response = await client.get("/api/users/1", headers=headers1)
        if response.status_code == 429:
            break
        assert response.status_code in [200, 404]

    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert "Rate limit exceeded" in response.json()["detail"]

    # Verify that user2 is not rate-limited
    response = await client.get("/api/users/2", headers=headers2)
    assert response.status_code in [200, 404]

    # Verify that an unauthenticated user is not rate-limited
    response = await client.get("/api/users/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rate_limit_api(client: AsyncClient):
    # The API endpoints have a limit of 60/minute.
    # We'll make 61 requests to trigger the rate limit.
    # We use a non-existent user to avoid side effects.
    for i in range(61):
        response = await client.get("/api/users/999")
        if response.status_code == 429:
            break
        # The endpoint will return 404 for a non-existent user, which is fine for this test.
        assert response.status_code == 404

    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert "Rate limit exceeded" in response.json()["detail"]


@pytest.mark.asyncio
async def test_rate_limit_login(client: AsyncClient):
    # The login endpoint has a stricter limit of 10/minute.
    # We'll make 11 requests to trigger the rate limit.
    for i in range(11):
        response = await client.post(
            "/auth/login/access-token",
            data={"username": "test@example.com", "password": "password"},
        )
        if response.status_code == 429:
            break
        # The endpoint will return 400 for incorrect credentials, which is fine for this test.
        assert response.status_code == 400

    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert "Rate limit exceeded" in response.json()["detail"]
