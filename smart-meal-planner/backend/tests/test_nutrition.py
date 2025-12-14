import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from app.main import app
from app.core.db import get_session
from app.models.all_models import User, UserNutritionGoal
from datetime import date

# Use a separate in-memory SQLite database for testing
DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def override_get_session():
    with Session(engine) as session:
        yield session


app.dependency_overrides[get_session] = override_get_session


@pytest.fixture(scope="module")
def client():
    SQLModel.metadata.create_all(engine)
    yield TestClient(app)
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def test_user(db_session):
    user = User(email="test@example.com", hashed_password="hashed_password", postal_code="H4T1V6", household_size=2)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_create_nutrition_goal(client, test_user):
    from app.core.security import get_current_active_user

    def override_get_current_active_user():
        return test_user

    app.dependency_overrides[get_current_active_user] = override_get_current_active_user

    response = client.post(
        "/api/users/me/nutrition-goal",
        json={"goal_type": "weight_loss", "target_calories": 2000}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["goal_type"] == "weight_loss"
    assert data["target_calories"] == 2000
    assert data["user_id"] == test_user.id

def test_get_nutrition_goal(client, test_user, db_session):
    # First, create a goal to get
    goal = UserNutritionGoal(user_id=test_user.id, goal_type="weight_loss", target_calories=2000)
    db_session.add(goal)
    db_session.commit()

    from app.core.security import get_current_active_user
    app.dependency_overrides[get_current_active_user] = lambda: test_user

    response = client.get("/api/users/me/nutrition-goal")
    assert response.status_code == 200
    data = response.json()
    assert data["goal_type"] == "weight_loss"

def test_update_nutrition_goal(client, test_user, db_session):
    # First, create a goal to update
    goal = UserNutritionGoal(user_id=test_user.id, goal_type="weight_loss", target_calories=2000)
    db_session.add(goal)
    db_session.commit()

    from app.core.security import get_current_active_user
    app.dependency_overrides[get_current_active_user] = lambda: test_user

    response = client.post(
        "/api/users/me/nutrition-goal",
        json={"goal_type": "muscle_gain", "target_protein": 150}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["goal_type"] == "muscle_gain"
    assert data["target_protein"] == 150

def test_get_nutrition_summary(client, test_user):
    from app.core.security import get_current_active_user
    app.dependency_overrides[get_current_active_user] = lambda: test_user

    start_date = date(2023, 1, 1).isoformat()
    end_date = date(2023, 1, 7).isoformat()
    response = client.get(f"/api/users/me/nutrition-summary?start_date={start_date}&end_date={end_date}")
    assert response.status_code == 200
    assert response.json() == []

    app.dependency_overrides = {}
