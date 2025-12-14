from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# --- Sync Engine (Keep for Celery & Migrations) ---
connection_string = settings.SQLALCHEMY_DATABASE_URI
if connection_string and connection_string.startswith("postgres://"):
    connection_string = connection_string.replace("postgres://", "postgresql://", 1)

connect_args = {}
if settings.SQLALCHEMY_DATABASE_URI and "sqlite" in settings.SQLALCHEMY_DATABASE_URI:
    connect_args["check_same_thread"] = False

engine = create_engine(connection_string, connect_args=connect_args, echo=True)

# --- Async Engine (For API) ---
# Create async connection string
async_connection_string = connection_string
if "postgresql://" in async_connection_string:
    async_connection_string = async_connection_string.replace("postgresql://", "postgresql+asyncpg://")
elif "sqlite://" in async_connection_string:
    async_connection_string = async_connection_string.replace("sqlite://", "sqlite+aiosqlite://")

async_engine = create_async_engine(async_connection_string, echo=True)

async def get_async_session():
    async_session = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session

def get_session():
    """Sync session for Celery or background threads."""
    with Session(engine) as session:
        yield session

def init_db():
    SQLModel.metadata.create_all(engine)
