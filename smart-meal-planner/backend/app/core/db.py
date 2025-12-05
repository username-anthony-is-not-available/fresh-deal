from sqlmodel import SQLModel, create_engine, Session
from app.core.config import settings

# Handle the case where the connection string might be for postgres (starts with postgres://)
# SQLAlchemy 1.4+ requires postgresql://
connection_string = settings.SQLALCHEMY_DATABASE_URI
if connection_string and connection_string.startswith("postgres://"):
    connection_string = connection_string.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if "sqlite" in connection_string else {}

engine = create_engine(connection_string, connect_args=connect_args, echo=True)

def get_session():
    with Session(engine) as session:
        yield session

def init_db():
    SQLModel.metadata.create_all(engine)
