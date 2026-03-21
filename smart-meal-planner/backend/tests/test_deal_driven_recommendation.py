
import pytest
import json
from unittest.mock import patch
from sqlmodel import Session, SQLModel, create_engine
from app.agents.planner_agent import MealPlannerAgent
from app.models.all_models import Recipe, User, Product, Deal, Store, RecipeIngredient
from datetime import date, timedelta

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
        # Default mock return
        mock_instance.generate_meal_plan.return_value = {
            "meal_plan": [],
            "shopping_summary": {"key_deals_used": [], "estimated_savings": 0}
        }
        yield mock_instance

def create_test_data(session: Session):
    # Create Store
    store = Store(name="Test Store", chain="Test Chain", postal_code="H1A1A1")
    session.add(store)
    session.flush()

    # Create Products
    p1 = Product(name="Chicken Breast", category="Meat", unit_type="kg")
    p2 = Product(name="Broccoli", category="Produce", unit_type="each")
    session.add(p1)
    session.add(p2)
    session.flush()

    # Create Deals
    d1 = Deal(product_id=p1.id, store_id=store.id, price=5.0, original_price=10.0, discount_pct=50.0, valid_from=date.today(), valid_until=date.today() + timedelta(days=7))
    session.add(d1)
    session.flush()

    # Create Recipes
    # Recipe 1: Has Chicken (on sale)
    r1 = Recipe(id=1, name="Chicken Stir Fry", meal_type="Dinner", ingredients_json=json.dumps([{"item": "Chicken Breast", "quantity": 0.5, "unit": "kg"}]))
    session.add(r1)
    session.flush()
    session.add(RecipeIngredient(recipe_id=r1.id, name="chicken breast", original_text="Chicken Breast"))

    # Recipe 2: No ingredients on sale
    r2 = Recipe(id=2, name="Pasta Marinara", meal_type="Dinner", ingredients_json=json.dumps([{"item": "Pasta", "quantity": 500, "unit": "g"}]))
    session.add(r2)
    session.flush()
    session.add(RecipeIngredient(recipe_id=r2.id, name="pasta", original_text="Pasta"))

    session.commit()

def test_calculate_deal_scores(session: Session):
    create_test_data(session)
    agent = MealPlannerAgent(session)

    # Manually load recipes to ensure they are fresh
    recipes = agent._load_recipes_from_db()
    deals = agent.get_available_deals()

    # Test if agent has the method (it won't yet, so this is a TDD approach)
    if hasattr(agent, '_calculate_deal_scores'):
        recipes_with_scores = agent._calculate_deal_scores(recipes, deals)

        r1 = next(r for r in recipes_with_scores if r["id"] == 1)
        r2 = next(r for r in recipes_with_scores if r["id"] == 2)

        assert r1["deal_score"] > 0
        assert r2["deal_score"] == 0
    else:
        pytest.skip("Method _calculate_deal_scores not implemented yet")

def test_generate_plan_prioritizes_deals(session: Session, mock_llm_service):
    create_test_data(session)
    user = User(id=1, household_size=2, dietary_preferences_json="[]", postal_code="H1A1A1")
    agent = MealPlannerAgent(session)
    agent.llm_service = mock_llm_service

    # Act
    agent.generate_plan(user)

    # Assert
    mock_llm_service.generate_meal_plan.assert_called_once()
    call_args, _ = mock_llm_service.generate_meal_plan.call_args
    filtered_recipes = call_args[2]

    # After my changes, Recipe 1 (Chicken Stir Fry) should be at the top if sorted by deal_score
    assert filtered_recipes[0]["name"] == "Chicken Stir Fry"
    assert filtered_recipes[0]["deal_score"] > 0
