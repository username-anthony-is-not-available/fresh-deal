
import os
os.environ["USE_SQLITE_LOCAL"] = "True"
os.environ["USE_MOCK_AI"] = "True"

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from app.main import app
from app.core.db import get_session
from app.models.all_models import User

# In-memory SQLite for testing
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_test_session():
    with Session(engine) as session:
        yield session

app.dependency_overrides[get_session] = get_test_session

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Smart Meal Planner API is running"}

def test_full_flow():
    create_db_and_tables()

    # 1. Onboard
    response = client.post(
        "/api/onboard",
        json={"postal_code": "H4T 1V6", "household_size": 2, "dietary_preferences": "None"}
    )
    assert response.status_code == 200
    user_id = response.json()["id"]

    # 2. Seed Data
    response = client.post("/api/data/seed")
    assert response.status_code == 200

    # 3. Generate Plan
    response = client.post(f"/api/plans/generate?user_id={user_id}")
    assert response.status_code == 200
    data = response.json()
    assert "days" in data
    assert len(data["days"]) == 7
    assert "shopping_list_summary" in data
