import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from app.main import app
from app.core.db import get_async_session

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture(name="session")
async def session_fixture():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

@pytest_asyncio.fixture(name="client")
async def client_fixture(session: AsyncSession):
    def get_session_override():
        return session

    app.dependency_overrides[get_async_session] = get_session_override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_async_session, None)
