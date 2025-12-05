
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
            {"name": "IGA Extra", "chain": "IGA", "postal_code": "H4T 1V6"},
            {"name": "Metro Plus", "chain": "Metro", "postal_code": "H4T 1V6"},
            {"name": "Maxi", "chain": "Maxi", "postal_code": "H4T 1V6"}
        ]

        self.categories = {
            "Produce": [
                "Apples (Gala)", "Apples (Macintosh)", "Bananas", "Carrots (2lb)", "Spinach",
                "Potatoes (Russet)", "Potatoes (Red)", "Broccoli Crowns", "Tomatoes (Beefsteak)",
                "Onions (Yellow)", "Red Peppers", "Green Peppers", "Cucumber", "Zucchini",
                "Strawberries", "Blueberries", "Raspberries", "Avocado", "Lettuce (Romaine)",
                "Mushrooms (White)", "Garlic (3 pack)", "Sweet Potatoes", "Celery Stalks",
                "Cauliflower", "Green Beans"
            ],
            "Meat": [
                "Ground Beef (Lean)", "Ground Beef (Medium)", "Chicken Thighs (Bone-in)",
                "Chicken Breast (Boneless)", "Pork Chops", "Pork Tenderloin",
                "Salmon Fillet (Atlantic)", "Bacon (375g)", "Sausages (Italian)",
                "Steak (Striploin)", "Steak (Ribeye)", "Whole Chicken", "Ground Turkey"
            ],
            "Seafood": [
                "Shrimp (Frozen)", "Tilapia Fillets", "Haddock Fillets", "Smoked Salmon"
            ],
            "Dairy & Alternatives": [
                "Milk (2L) 2%", "Milk (2L) 3.25%", "Eggs (12 Large)", "Cheddar Cheese (Old)",
                "Cheddar Cheese (Medium)", "Mozzarella Cheese", "Yogurt (Greek 750g)",
                "Yogurt (Vanilla 650g)", "Butter (Salted)", "Butter (Unsalted)",
                "Cream (10%)", "Sour Cream", "Oat Milk", "Almond Milk", "Tofu (Firm)"
            ],
            "Pantry": [
                "Rice (Basmati 2kg)", "Rice (Jasmine 2kg)", "Pasta (Spaghetti 900g)",
                "Pasta (Penne 900g)", "Canned Beans (Black)", "Canned Beans (Chickpeas)",
                "Tomato Sauce (Can)", "Diced Tomatoes", "Bread (Whole Wheat)",
                "Bread (White)", "Flour (All Purpose 2.5kg)", "Sugar (White 2kg)",
                "Olive Oil (1L)", "Vegetable Oil (2L)", "Peanut Butter", "Jam (Strawberry)",
                "Cereal (Cheerios)", "Oats (Quick)", "Quinoa", "Lentils (Dry)"
            ],
            "Frozen": [
                "Frozen Peas", "Frozen Corn", "Frozen Mixed Veggies", "Pizza (Delissio)",
                "Ice Cream (Vanilla)", "Frozen Berries"
            ],
            "Snacks": [
                "Potato Chips", "Pretzels", "Almonds", "Granola Bars", "Crackers"
            ]
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
                    lower_name = item_name.lower()
                    if any(x in lower_name for x in ["beef", "chicken", "pork", "salmon", "steak", "fillet"]):
                        unit = "kg"
                    elif any(x in lower_name for x in ["apples", "potatoes", "onions", "peppers", "bananas"]):
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

        # Simple cleanup of old deals (mock logic)
        existing_deals = self.session.exec(select(Deal)).all()
        for d in existing_deals:
             self.session.delete(d)
        self.session.commit()

        today = date.today()
        next_week = today + timedelta(days=7)

        deals_created = 0

        for product in products:
            # 50% chance of a deal for any given product at A store
            # But we want to simulate multiple stores having different deals

            # Iterate through stores and randomly assign deals
            for store in stores:
                 # 20% chance this specific store has this item on sale
                 if random.random() < 0.20:
                    # Base price simulation
                    base_price = 0.0
                    if product.category == "Meat": base_price = random.uniform(8.0, 25.0)
                    elif product.category == "Seafood": base_price = random.uniform(12.0, 30.0)
                    elif product.category == "Dairy & Alternatives": base_price = random.uniform(4.0, 10.0)
                    elif product.category == "Produce": base_price = random.uniform(1.5, 6.0)
                    elif product.category == "Pantry": base_price = random.uniform(2.0, 12.0)
                    else: base_price = random.uniform(3.0, 9.0)

                    discount_pct = random.choice([0.10, 0.20, 0.25, 0.30, 0.40, 0.50])
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
