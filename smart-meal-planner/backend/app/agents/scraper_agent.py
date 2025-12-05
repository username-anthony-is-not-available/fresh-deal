
import random
from datetime import date, timedelta
from sqlmodel import Session, select
from app.models.all_models import Product, Store, Deal

class MockScraperAgent:
    def __init__(self, session: Session):
        self.session = session

        # Store definitions with characteristics
        self.store_configs = {
            "Walmart": {
                "names": ["Walmart Supercentre"],
                "base_price_multiplier": 0.90, # Generally cheaper
                "deal_frequency": 0.3,
                "exclusive_categories": ["Pantry", "Household"],
                "brands": ["Great Value", "Equate"]
            },
            "Provigo": {
                "names": ["Provigo Le Marché"],
                "base_price_multiplier": 1.10, # Premium
                "deal_frequency": 0.25,
                "exclusive_categories": ["Deli", "Bakery"],
                "brands": ["President's Choice", "No Name"]
            },
            "IGA": {
                "names": ["IGA Extra"],
                "base_price_multiplier": 1.15, # Premium
                "deal_frequency": 0.2,
                "exclusive_categories": ["Local", "Gourmet"],
                "brands": ["Compliments"]
            },
            "Metro": {
                "names": ["Metro Plus"],
                "base_price_multiplier": 1.12,
                "deal_frequency": 0.25,
                "exclusive_categories": ["Bakery", "Meat"],
                "brands": ["Selection", "Irresistibles"]
            },
            "Maxi": {
                "names": ["Maxi"],
                "base_price_multiplier": 0.85, # Discount
                "deal_frequency": 0.4,
                "exclusive_categories": ["Bulk", "Frozen"],
                "brands": ["No Name", "President's Choice"]
            }
        }

        self.stores_data = [
            {"name": "Walmart Supercentre", "chain": "Walmart", "postal_code": "H4T 1V6"},
            {"name": "Provigo Le Marché", "chain": "Provigo", "postal_code": "H4T 1V6"},
            {"name": "IGA Extra", "chain": "IGA", "postal_code": "H4T 1V6"},
            {"name": "Metro Plus", "chain": "Metro", "postal_code": "H4T 1V6"},
            {"name": "Maxi", "chain": "Maxi", "postal_code": "H4T 1V6"}
        ]

        # Expanded Product Catalog
        self.categories = {
            "Produce": [
                "Apples (Gala)", "Apples (Macintosh)", "Bananas", "Carrots (2lb)", "Spinach",
                "Potatoes (Russet)", "Potatoes (Red)", "Broccoli Crowns", "Tomatoes (Beefsteak)",
                "Onions (Yellow)", "Red Peppers", "Green Peppers", "Cucumber", "Zucchini",
                "Strawberries", "Blueberries", "Raspberries", "Avocado", "Lettuce (Romaine)",
                "Mushrooms (White)", "Garlic (3 pack)", "Sweet Potatoes", "Celery Stalks",
                "Cauliflower", "Green Beans", "Kale", "Asparagus", "Brussels Sprouts"
            ],
            "Meat": [
                "Ground Beef (Lean)", "Ground Beef (Medium)", "Chicken Thighs (Bone-in)",
                "Chicken Breast (Boneless)", "Pork Chops", "Pork Tenderloin",
                "Salmon Fillet (Atlantic)", "Bacon (375g)", "Sausages (Italian)",
                "Steak (Striploin)", "Steak (Ribeye)", "Whole Chicken", "Ground Turkey",
                "Lamb Chops", "Chicken Drumsticks"
            ],
            "Seafood": [
                "Shrimp (Frozen)", "Tilapia Fillets", "Haddock Fillets", "Smoked Salmon", "Cod Fillets"
            ],
            "Dairy & Alternatives": [
                "Milk (2L) 2%", "Milk (2L) 3.25%", "Eggs (12 Large)", "Cheddar Cheese (Old)",
                "Cheddar Cheese (Medium)", "Mozzarella Cheese", "Yogurt (Greek 750g)",
                "Yogurt (Vanilla 650g)", "Butter (Salted)", "Butter (Unsalted)",
                "Cream (10%)", "Sour Cream", "Oat Milk", "Almond Milk", "Tofu (Firm)",
                "Parmesan Cheese", "Cottage Cheese"
            ],
            "Pantry": [
                "Rice (Basmati 2kg)", "Rice (Jasmine 2kg)", "Pasta (Spaghetti 900g)",
                "Pasta (Penne 900g)", "Canned Beans (Black)", "Canned Beans (Chickpeas)",
                "Tomato Sauce (Can)", "Diced Tomatoes", "Bread (Whole Wheat)",
                "Bread (White)", "Flour (All Purpose 2.5kg)", "Sugar (White 2kg)",
                "Olive Oil (1L)", "Vegetable Oil (2L)", "Peanut Butter", "Jam (Strawberry)",
                "Cereal (Cheerios)", "Oats (Quick)", "Quinoa", "Lentils (Dry)",
                "Soy Sauce", "Chicken Broth", "Beef Broth", "Honey", "Maple Syrup"
            ],
            "Frozen": [
                "Frozen Peas", "Frozen Corn", "Frozen Mixed Veggies", "Pizza (Delissio)",
                "Ice Cream (Vanilla)", "Frozen Berries", "Frozen Fries", "Frozen Spinach"
            ],
            "Snacks": [
                "Potato Chips", "Pretzels", "Almonds", "Granola Bars", "Crackers", "Popcorn"
            ]
        }

    def seed_stores(self):
        created_stores = []
        for s_data in self.stores_data:
            existing = self.session.exec(select(Store).where(Store.name == s_data["name"])).first()
            if not existing:
                store = Store(**s_data)
                self.session.add(store)
                created_stores.append(store)
            else:
                created_stores.append(existing)
        self.session.commit()
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
                    if any(x in lower_name for x in ["beef", "chicken", "pork", "salmon", "steak", "fillet", "turkey", "lamb", "cod", "tilapia", "haddock"]):
                        unit = "kg"
                    elif any(x in lower_name for x in ["apples", "potatoes", "onions", "peppers", "bananas", "sweet potatoes"]):
                        unit = "lb"
                    elif any(x in lower_name for x in ["milk", "oil", "juice", "cream", "broth"]):
                        unit = "L"

                    prod = Product(name=item_name, category=cat, unit_type=unit)
                    self.session.add(prod)
                    created_products.append(prod)
                else:
                    created_products.append(existing)
        self.session.commit()
        for p in created_products:
            self.session.refresh(p)
        return created_products

    def get_base_price(self, product, chain_config):
        # Base price simulation
        base = 0.0
        if product.category == "Meat": base = random.uniform(8.0, 25.0)
        elif product.category == "Seafood": base = random.uniform(12.0, 30.0)
        elif product.category == "Dairy & Alternatives": base = random.uniform(4.0, 10.0)
        elif product.category == "Produce": base = random.uniform(1.5, 6.0)
        elif product.category == "Pantry": base = random.uniform(2.0, 12.0)
        else: base = random.uniform(3.0, 9.0)

        # Apply chain multiplier
        adjusted_base = base * chain_config["base_price_multiplier"]
        return round(adjusted_base, 2)

    def generate_deals(self):
        stores = self.seed_stores()
        products = self.seed_products()

        # Cleanup of old deals
        existing_deals = self.session.exec(select(Deal)).all()
        for d in existing_deals:
             self.session.delete(d)
        self.session.commit()

        today = date.today()
        next_week = today + timedelta(days=7)

        deals_created = 0

        for product in products:
            for store in stores:
                chain_config = self.store_configs.get(store.chain, self.store_configs["Walmart"]) # Default to Walmart config

                # 1. Check availability (Simulate distinct inventory)
                # Not every product is at every store.
                # Let's say 90% availability for Walmart/Maxi/Provigo, 80% for IGA/Metro
                availability_chance = 0.95
                if store.chain in ["IGA", "Metro"]:
                     availability_chance = 0.85

                # Some exclusive logic could go here, but random availability is good for MVP differentiation
                if random.random() > availability_chance:
                    continue

                base_price = self.get_base_price(product, chain_config)

                # 2. Determine if it's a deal
                is_deal = False
                deal_price = base_price
                discount_pct = 0.0

                if random.random() < chain_config["deal_frequency"]:
                    is_deal = True
                    discount_pct = random.choice([0.10, 0.20, 0.25, 0.30, 0.40, 0.50])
                    # Loss leaders for Milk/Eggs/Butter at certain stores
                    if product.name in ["Milk (2L) 2%", "Eggs (12 Large)", "Butter (Salted)"] and store.chain in ["Maxi", "Walmart"]:
                         if random.random() < 0.5:
                             discount_pct = 0.40 # Deep discount

                    deal_price = round(base_price * (1 - discount_pct), 2)
                    discount_int = int(discount_pct * 100)

                    deal = Deal(
                        product_id=product.id,
                        store_id=store.id,
                        price=deal_price,
                        original_price=base_price,
                        discount_pct=discount_int,
                        valid_from=today,
                        valid_until=next_week
                    )
                    self.session.add(deal)
                    deals_created += 1
                else:
                    # Create a "regular price" deal entry (0% off) so the optimizer knows the price at this store
                    # In a real system, we'd have a separate ProductPrice table, but for this MVP,
                    # we can treat regular prices as 0% discount deals or just have a way to look them up.
                    # The BRD/Schema implies Deals table holds the pricing info.
                    # If we only store "Deals", we won't know the price if it's not on sale.
                    # Let's add a "regular price" entry with 0 discount to represent shelf price availability.

                    deal = Deal(
                        product_id=product.id,
                        store_id=store.id,
                        price=base_price,
                        original_price=base_price,
                        discount_pct=0,
                        valid_from=today,
                        valid_until=next_week
                    )
                    self.session.add(deal)
                    # We won't count this as a "deal created" for the return value, or maybe we should?
                    # The return value is just for logging.

        self.session.commit()
        return deals_created
