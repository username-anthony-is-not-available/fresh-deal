"""Tests for expanded dietary restriction nutritional tracking (Issue #391)."""

from datetime import date, datetime, timedelta, timezone
import json
from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.db import get_session
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.all_models import DailyNutrition, MealPlan, User, UserNutritionGoal
from app.services.dietary_nutrition_service import DietaryNutritionService


@pytest.fixture
def client_and_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="dietary@example.com",
            hashed_password=get_password_hash("password123"),
            postal_code="H4T1V6",
            household_size=2,
            dietary_preferences_json=json.dumps(["keto", "low_sodium"]),
            allergies_json=json.dumps(["peanuts"]),
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        def override_session():
            yield session

        app.dependency_overrides[get_session] = override_session
        token = create_access_token(subject=str(user.id))
        headers = {"Authorization": f"Bearer {token}"}
        with TestClient(app) as client:
            yield client, session, user, headers
        app.dependency_overrides.clear()


def test_supported_dietary_profiles_cover_expanded_restrictions():
    """DietaryNutritionService lists expanded restrictions beyond the original 5."""
    profiles = DietaryNutritionService.list_supported_profiles()
    keys = {p["key"] for p in profiles}
    assert {
        "vegetarian",
        "vegan",
        "pescatarian",
        "gluten-free",
        "dairy-free",
        "keto",
        "low-carb",
        "paleo",
        "halal",
        "kosher",
        "nut-free",
        "low-sodium",
        "high-protein",
        "mediterranean",
    }.issubset(keys)


def test_compute_recommended_targets_adapts_to_keto_and_vegan():
    """Recommended targets adjust carb caps for keto and high fiber/carbs for vegan."""
    keto_targets = DietaryNutritionService.compute_recommended_targets(
        goal_type="weight_loss",
        restrictions=["keto", "low_sodium"],
        base_calories=1800,
    )
    assert keto_targets["target_carbs"] <= 50.0
    assert keto_targets["max_sodium_mg"] == 1500.0
    assert "magnesium" in keto_targets["micronutrients_to_watch"]

    vegan_targets = DietaryNutritionService.compute_recommended_targets(
        goal_type="maintenance",
        restrictions=["vegan"],
    )
    assert vegan_targets["target_fiber"] >= 32.0
    assert "vitamin_b12" in vegan_targets["micronutrients_to_watch"]


def test_nutrition_api_recommended_goal_and_compliance_evaluation(client_and_session):
    """API endpoints compute recommended goals, persist optional targets, and detect violations."""
    client, session, user, headers = client_and_session

    profiles_resp = client.get("/api/nutrition/dietary-profiles")
    assert profiles_resp.status_code == 200
    assert len(profiles_resp.json()) >= 14

    rec_resp = client.post(
        "/api/users/me/nutrition-goal/recommended",
        json={"goal_type": "maintenance", "base_calories": 2000, "apply_to_goal": True},
        headers=headers,
    )
    assert rec_resp.status_code == 200
    rec_data = rec_resp.json()
    assert rec_data["target_carbs"] <= 50.0
    assert rec_data["max_sodium_mg"] == 1500.0

    # Verify applied to UserNutritionGoal
    goal_resp = client.get("/api/users/me/nutrition-goal", headers=headers)
    assert goal_resp.status_code == 200
    assert goal_resp.json()["target_carbs"] == rec_data["target_carbs"]

    # Insert high-carb/high-sodium intake and peanut-containing meal plan to verify warnings & conflicts
    today = date.today()
    session.add(
        DailyNutrition(
            user_id=user.id,
            date=today,
            calories=2100,
            protein=120,
            carbs=140,
            fats=110,
            fiber=12,
            micronutrients_json=json.dumps({"sodium_mg": 2200}),
        )
    )
    session.add(
        MealPlan(
            user_id=user.id,
            start_date=today,
            end_date=today + timedelta(days=6),
            content_json=json.dumps(
                {
                    "days": [
                        {
                            "meals": [
                                {"name": "Peanut Pasta Bowl", "ingredients": ["pasta", "peanut sauce"]}
                            ]
                        }
                    ]
                }
            ),
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    session.commit()

    comp_resp = client.get("/api/users/me/nutrition-compliance?days=7", headers=headers)
    assert comp_resp.status_code == 200
    comp = comp_resp.json()
    assert comp["compliance_score"] < 80
    assert comp["status"] in ("attention", "non_compliant")
    assert any("ketogenic limit" in w for w in comp["warnings"])
    assert any("low-sodium limit" in w for w in comp["warnings"])
    assert any(c["type"] == "allergen" and "peanuts" in c["restriction"] for c in comp["conflicts"])
