import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from app.main import app
from app.core.db import get_session
from app.models.all_models import User, UserNutritionGoal, DailyNutrition
from datetime import date

# Use a separate in-memory SQLite database for testing
DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@pytest.fixture(name="session_client", scope="function")
def session_client_fixture():
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    client = TestClient(app)

    yield client

    SQLModel.metadata.drop_all(engine)
    app.dependency_overrides.clear()


@pytest.fixture(name="test_user", scope="function")
def test_user_fixture():
    with Session(engine) as session:
        user = User(email="test@example.com", hashed_password="hashed_password", postal_code="H4T1V6", household_size=2)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def test_create_nutrition_goal(session_client, test_user):
    from app.core.security import get_current_active_user
    app.dependency_overrides[get_current_active_user] = lambda: test_user

    response = session_client.post(
        "/api/users/me/nutrition-goal",
        json={"goal_type": "weight_loss", "target_calories": 2000}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["goal_type"] == "weight_loss"
    assert data["target_calories"] == 2000
    assert data["user_id"] == test_user.id

def test_get_nutrition_goal(session_client, test_user):
    with Session(engine) as session:
        goal = UserNutritionGoal(user_id=test_user.id, goal_type="weight_loss", target_calories=2000)
        session.add(goal)
        session.commit()

    from app.core.security import get_current_active_user
    app.dependency_overrides[get_current_active_user] = lambda: test_user

    response = session_client.get("/api/users/me/nutrition-goal")
    assert response.status_code == 200
    data = response.json()
    assert data["goal_type"] == "weight_loss"

def test_update_nutrition_goal(session_client, test_user):
    with Session(engine) as session:
        goal = UserNutritionGoal(user_id=test_user.id, goal_type="weight_loss", target_calories=2000)
        session.add(goal)
        session.commit()

    from app.core.security import get_current_active_user
    app.dependency_overrides[get_current_active_user] = lambda: test_user

    response = session_client.post(
        "/api/users/me/nutrition-goal",
        json={"goal_type": "muscle_gain", "target_protein": 150}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["goal_type"] == "muscle_gain"
    assert data["target_protein"] == 150

def test_get_nutrition_summary(session_client, test_user):
    from app.core.security import get_current_active_user
    app.dependency_overrides[get_current_active_user] = lambda: test_user

    response = session_client.get(f"/api/users/{test_user.id}/nutrition-summary")
    assert response.status_code == 404
