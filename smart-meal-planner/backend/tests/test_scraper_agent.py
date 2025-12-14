
import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from app.agents.scraper_agent import MockScraperAgent
from app.models.all_models import Store, Product, Deal

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

def test_seed_stores(session: Session):
    # Arrange
    agent = MockScraperAgent(session)

    # Act
    agent.seed_stores()

    # Assert
    stores = session.exec(select(Store)).all()
    assert len(stores) == 5
    assert stores[0].name == "Walmart Supercentre"

def test_seed_products(session: Session):
    # Arrange
    agent = MockScraperAgent(session)

    # Act
    agent.seed_products()

    # Assert
    products = session.exec(select(Product)).all()
    # The number of products is the sum of items in all categories
    total_products = sum(len(items) for items in agent.categories.values())
    assert len(products) == total_products

def test_generate_deals(session: Session):
    # Arrange
    agent = MockScraperAgent(session)

    # Act
    deals_created = agent.generate_deals()

    # Assert
    deals = session.exec(select(Deal)).all()
    stores = session.exec(select(Store)).all()
    products = session.exec(select(Product)).all()

    assert len(stores) > 0
    assert len(products) > 0
    assert len(deals) > 0
    # Check that at least some deals have a discount
    assert any(deal.discount_pct > 0 for deal in deals)
    assert deals_created > 0
