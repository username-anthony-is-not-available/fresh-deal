import random
from datetime import date, timedelta
from sqlmodel import Session, select
from app.models.all_models import Store, Product, Deal

class MockScraperAgent:
    def __init__(self, session: Session):
        self.session = session

    def generate_deals(self) -> int:
        """Generates mock deals for stores and products."""
        stores_data = [
            {"name": "Walmart", "chain": "Walmart", "postal_code": "H4T1V6"},
            {"name": "Provigo", "chain": "Provigo", "postal_code": "H4B2T8"},
            {"name": "IGA", "chain": "IGA", "postal_code": "H4B1W3"},
            {"name": "Metro", "chain": "Metro", "postal_code": "H4B1W3"},
            {"name": "Maxi", "chain": "Maxi", "postal_code": "H4B1W3"},
        ]

        products_data = [
            {"name": "Chicken Breast", "category": "Meat", "unit_type": "kg"},
            {"name": "Salmon Fillet", "category": "Seafood", "unit_type": "kg"},
            {"name": "Milk", "category": "Dairy", "unit_type": "L"},
            {"name": "Eggs", "category": "Dairy", "unit_type": "dozen"},
            {"name": "Bread", "category": "Bakery", "unit_type": "loaf"},
            {"name": "Apples", "category": "Produce", "unit_type": "kg"},
            {"name": "Bananas", "category": "Produce", "unit_type": "kg"},
            {"name": "Spinach", "category": "Produce", "unit_type": "g"},
        ]

        # Create stores and products if they don't exist
        for store_info in stores_data:
            statement = select(Store).where(Store.name == store_info["name"])
            if not self.session.exec(statement).first():
                self.session.add(Store(**store_info))

        for product_info in products_data:
            statement = select(Product).where(Product.name == product_info["name"])
            if not self.session.exec(statement).first():
                self.session.add(Product(**product_info))

        self.session.commit()

        # Generate deals
        stores = self.session.exec(select(Store)).all()
        products = self.session.exec(select(Product)).all()

        deals = []
        for _ in range(50):  # Generate 50 mock deals
            store = random.choice(stores)
            product = random.choice(products)
            price = round(random.uniform(2.5, 20.0), 2)
            original_price = round(price * random.uniform(1.1, 1.5), 2)

            deal = Deal(
                product_id=product.id,
                store_id=store.id,
                price=price,
                original_price=original_price,
                valid_from=date.today(),
                valid_until=date.today() + timedelta(days=7),
            )
            deals.append(deal)

        self.session.add_all(deals)
        self.session.commit()
        return len(deals)
