
import pytest
import json
from unittest.mock import MagicMock, patch
from sqlmodel import Session, SQLModel, create_engine
from app.agents.planner_agent import MealPlannerAgent
from app.models.all_models import Recipe, User

# In-memory SQLite database for testing
engine = create_engine("sqlite:///:memory:")

def setup_database():
    SQLModel.metadata.create_all(engine)

def teardown_database():
    SQLModel.metadata.drop_all(engine)

@pytest.fixture(name="session")
def session_fixture():
    setup_database()
    with Session(engine) as session:
        yield session
    teardown_database()

@pytest.fixture
def mock_llm_service():
    with patch("app.agents.planner_agent.LLMService") as mock:
        mock_instance = mock.return_value
        mock_instance.generate_meal_plan.return_value = {
            "meal_plan": [
                {
                    "day": 1,
                    "breakfast": {"recipe_id": 1, "recipe_name": "Scrambled Eggs"},
                    "lunch": {"recipe_id": 2, "recipe_name": "Chicken Salad"},
                    "dinner": {"recipe_id": 3, "recipe_name": "Spaghetti Bolognese"},
                }
            ]
        }
        yield mock_instance

def create_test_recipes(session: Session):
    recipes_data = [
        {"id": 1, "name": "Scrambled Eggs", "meal_type": "Breakfast", "ingredients_json": "[]", "instructions_json": "[]"},
        {"id": 2, "name": "Chicken Salad", "meal_type": "Lunch", "ingredients_json": "[]", "instructions_json": "[]"},
        {"id": 3, "name": "Spaghetti Bolognese", "meal_type": "Dinner", "ingredients_json": "[]", "instructions_json": "[]"},
    ]
    for data in recipes_data:
        session.add(Recipe(**data))
    session.commit()

def test_generate_plan_llm_success(session: Session, mock_llm_service):
    # Arrange
    create_test_recipes(session)
    user = User(id=1, household_size=2, dietary_preferences="None", postal_code="H1A1A1")
    agent = MealPlannerAgent(session)
    agent.llm_service = mock_llm_service

    # Act
    plan = agent.generate_plan(user)

    # Assert
    assert "meal_plan" in plan
    assert len(plan["meal_plan"]) == 1
    assert plan["meal_plan"][0]["breakfast"]["recipe_name"] == "Scrambled Eggs"
    mock_llm_service.generate_meal_plan.assert_called_once()

def test_generate_plan_llm_failure_fallback(session: Session, mock_llm_service):
    # Arrange
    create_test_recipes(session)
    user = User(id=1, household_size=2, dietary_preferences="None", postal_code="H1A1A1")

    # Simulate LLM failure
    mock_llm_service.generate_meal_plan.side_effect = Exception("LLM API is down")

    agent = MealPlannerAgent(session)
    agent.llm_service = mock_llm_service

    # Act
    plan = agent.generate_plan(user)

    # Assert
    assert "meal_plan" in plan
    assert "shopping_summary" in plan
    assert plan["shopping_summary"]["weekly_overview"] == "Heuristic fallback plan."
    assert len(plan["meal_plan"]) == 7  # Fallback should generate a full week
    assert "recipe_name" in plan["meal_plan"][0]["breakfast"]

def test_load_recipes_from_db(session: Session):
    # Arrange
    create_test_recipes(session)
    agent = MealPlannerAgent(session)

    # Act
    loaded_recipes = agent._load_recipes_from_db()

    # Assert
    assert len(loaded_recipes) == 3
    assert loaded_recipes[0]["name"] == "Scrambled Eggs"
    assert "average_rating" in loaded_recipes[0]

def test_get_available_deals_empty(session: Session):
    # Arrange
    agent = MealPlannerAgent(session)

    # Act
    deals = agent.get_available_deals()

    # Assert
    assert deals == []

def test_generate_plan_filters_by_dietary_preferences(session: Session, mock_llm_service):
    # Arrange
    recipes_data = [
        {"id": 1, "name": "Scrambled Eggs", "meal_type": "Breakfast", "ingredients_json": "[]", "instructions_json": "[]", "dietary_tags_json": "[\"vegetarian\"]"},
        {"id": 2, "name": "Chicken Salad", "meal_type": "Lunch", "ingredients_json": "[]", "instructions_json": "[]", "dietary_tags_json": "[]"},
        {"id": 3, "name": "Spaghetti Bolognese", "meal_type": "Dinner", "ingredients_json": "[]", "instructions_json": "[]", "dietary_tags_json": "[]"},
        {"id": 4, "name": "Tofu Scramble", "meal_type": "Breakfast", "ingredients_json": "[]", "instructions_json": "[]", "dietary_tags_json": "[\"vegetarian\", \"vegan\"]"},
    ]
    for data in recipes_data:
        session.add(Recipe(**data))
    session.commit()

    user = User(id=1, household_size=1, dietary_preferences_json='["vegetarian"]', postal_code="H1A1A1")

    agent = MealPlannerAgent(session)
    agent.llm_service = mock_llm_service

    # Act
    agent.generate_plan(user)

    # Assert
    mock_llm_service.generate_meal_plan.assert_called_once()
    call_args, _ = mock_llm_service.generate_meal_plan.call_args
    filtered_recipes = call_args[2]

    assert len(filtered_recipes) == 2
    assert filtered_recipes[0]["name"] == "Scrambled Eggs"
    assert filtered_recipes[1]["name"] == "Tofu Scramble"

def test_generate_plan_filters_by_allergies(session: Session, mock_llm_service):
    # Arrange
    recipes_data = [
        {"id": 1, "name": "Safe Salad", "ingredients_json": "[]", "instructions_json": "[]", "allergens_json": "[]"},
        {"id": 2, "name": "Peanut Satay", "ingredients_json": "[]", "instructions_json": "[]", "allergens_json": "[\"peanuts\"]"},
        {"id": 3, "name": "Pasta with Gluten", "ingredients_json": "[]", "instructions_json": "[]", "allergens_json": "[\"gluten\"]"},
    ]
    for data in recipes_data:
        session.add(Recipe(**data))
    session.commit()

    user = User(id=1, household_size=1, dietary_preferences_json='[]', allergies_json='["peanuts"]', postal_code="H1A1A1")

    agent = MealPlannerAgent(session)
    agent.llm_service = mock_llm_service

    # Act
    agent.generate_plan(user)

    # Assert
    mock_llm_service.generate_meal_plan.assert_called_once()
    call_args, _ = mock_llm_service.generate_meal_plan.call_args
    filtered_recipes = call_args[2]

    assert len(filtered_recipes) == 2
    assert any(r["name"] == "Safe Salad" for r in filtered_recipes)
    assert any(r["name"] == "Pasta with Gluten" for r in filtered_recipes)
    assert not any(r["name"] == "Peanut Satay" for r in filtered_recipes)
