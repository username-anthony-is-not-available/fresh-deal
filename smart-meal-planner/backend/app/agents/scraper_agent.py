
import random
from datetime import date, timedelta
from sqlmodel import Session, select
from app.models.all_models import Product, Store, Deal

class MockScraperAgent:
    def __init__(self, session: Session):
        self.session = session
        self.stores = [
            {"name": "Walmart Supercentre", "chain": "Walmart", "postal_code": "H4T 1V6"},
            {"name": "Provigo Le Marché", "chain": "Provigo", "postal_code": "H4T 1V6"},
            {"name": "IGA Extra", "chain": "IGA", "postal_code": "H4T 1V6"}
        ]

        self.categories = {
            "Produce": ["Apples", "Bananas", "Carrots", "Spinach", "Potatoes", "Broccoli", "Tomatoes", "Onions"],
            "Meat": ["Ground Beef", "Chicken Thighs", "Pork Chops", "Salmon Fillet", "Bacon"],
            "Dairy": ["Milk (2L)", "Eggs (12)", "Cheddar Cheese", "Yogurt", "Butter"],
            "Pantry": ["Rice (2kg)", "Pasta (900g)", "Canned Beans", "Tomato Sauce", "Bread"]
        }

    def seed_stores(self):
        created_stores = []
        for s_data in self.stores:
            existing = self.session.exec(select(Store).where(Store.name == s_data["name"])).first()
            if not existing:
                store = Store(**s_data)
                self.session.add(store)
                created_stores.append(store)
            else:
                created_stores.append(existing)
        self.session.commit()
        # Reload to get IDs
        for s in created_stores:
            self.session.refresh(s)
        return created_stores

    def seed_products(self):
        created_products = []
        for cat, items in self.categories.items():
            for item_name in items:
                existing = self.session.exec(select(Product).where(Product.name == item_name)).first()
                if not existing:
                    # Determine unit type loosely
                    unit = "each"
                    if any(x in item_name.lower() for x in ["beef", "chicken", "pork", "salmon"]):
                        unit = "kg"
                    elif any(x in item_name.lower() for x in ["apples", "potatoes", "onions"]):
                        unit = "lb"

                    prod = Product(name=item_name, category=cat, unit_type=unit)
                    self.session.add(prod)
                    created_products.append(prod)
                else:
                    created_products.append(existing)
        self.session.commit()
        for p in created_products:
            self.session.refresh(p)
        return created_products

    def generate_deals(self):
        stores = self.seed_stores()
        products = self.seed_products()

        # Clear existing deals for clean slate (optional, but good for POC)
        # self.session.exec(delete(Deal))

        today = date.today()
        next_week = today + timedelta(days=7)

        deals_created = 0

        for product in products:
            # 40% chance of a deal
            if random.random() < 0.4:
                # Pick a random store
                store = random.choice(stores)

                # Base price simulation
                base_price = 0.0
                if product.category == "Meat": base_price = random.uniform(8.0, 25.0)
                elif product.category == "Dairy": base_price = random.uniform(4.0, 10.0)
                elif product.category == "Produce": base_price = random.uniform(1.5, 6.0)
                else: base_price = random.uniform(2.0, 8.0)

                discount_pct = random.choice([0.10, 0.20, 0.30, 0.40, 0.50])
                sale_price = round(base_price * (1 - discount_pct), 2)

                deal = Deal(
                    product_id=product.id,
                    store_id=store.id,
                    price=sale_price,
                    original_price=round(base_price, 2),
                    discount_pct=int(discount_pct * 100),
                    valid_from=today,
                    valid_until=next_week
                )
                self.session.add(deal)
                deals_created += 1

        self.session.commit()
        return deals_created
