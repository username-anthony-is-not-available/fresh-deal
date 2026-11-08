import random
import json
import os
from datetime import date, timedelta
from sqlmodel import Session, select
from app.models.all_models import Store, Product, Deal, Recipe, RecipeIngredient

class MockScraperAgent:
    def __init__(self, session: Session):
        self.session = session

    def seed_recipes(self) -> int:
        """Seeds recipes from data/recipes.json if no recipes exist."""
        existing = self.session.exec(select(Recipe)).first()
        if existing:
            return 0

        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(base_path, "data", "recipes.json")
        if not os.path.exists(file_path):
            return 0

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        count = 0
        for r in data:
            recipe = Recipe(
                name=r.get("name", "Untitled Recipe"),
                cuisine=r.get("cuisine"),
                category=r.get("category", "Main"),
                meal_type=r.get("meal_type", "Dinner"),
                ingredients_json=json.dumps(r.get("ingredients", [])),
                instructions_json=json.dumps(r.get("instructions", [])),
                allergens_json=json.dumps(r.get("allergens", [])),
                dietary_tags_json=json.dumps(r.get("dietary_tags", [])),
                nutrition_json=json.dumps(r.get("nutrition", {})),
                prep_time_minutes=r.get("prep_time_minutes", 30),
                difficulty=r.get("difficulty", "medium"),
                servings=r.get("servings", 4),
                image_url=r.get("image_url"),
                source_url=r.get("source_url")
            )
            self.session.add(recipe)
            self.session.flush()

            for ing in r.get("ingredients", []):
                item_name = ing.get("item", "") if isinstance(ing, dict) else str(ing)
                clean_name = item_name.lower().strip()
                if clean_name:
                    db_ing = RecipeIngredient(
                        recipe_id=recipe.id,
                        name=clean_name,
                        original_text=f"{ing.get('quantity', '')} {ing.get('unit', '')} {item_name}".strip() if isinstance(ing, dict) else item_name
                    )
                    self.session.add(db_ing)
            count += 1

        self.session.commit()
        return count

    def generate_deals(self) -> int:
        """Generates mock deals for stores and products and seeds recipes."""
        self.seed_recipes()

        stores_data = [
            {"name": "Walmart", "chain": "Walmart", "postal_code": "H4T1V6"},
            {"name": "Provigo", "chain": "Provigo", "postal_code": "H4E2G9"}, # ~4km from H4T
            {"name": "IGA", "chain": "IGA", "postal_code": "H3G1V3"}, # ~6km from H4T
            {"name": "Metro", "chain": "Metro", "postal_code": "H3Z1T5"}, # ~4.5km from H4T
            {"name": "Maxi", "chain": "Maxi", "postal_code": "H1A1A1"}, # ~20km from H4T
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
