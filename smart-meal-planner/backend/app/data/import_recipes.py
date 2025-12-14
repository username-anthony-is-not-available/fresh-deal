
import json
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlmodel import Session, select
from app.models.all_models import Recipe, RecipeIngredient
from app.core.config import settings

logger = logging.getLogger(__name__)

class RecipeImporter:
    def __init__(self, session: Session):
        self.session = session

    def import_recipes(self, recipes_data: List[Dict[str, Any]]):
        """
        Imports a list of recipes in the Kaggle format.
        Expected keys: 'title', 'ingredients' (list), 'directions' (list), 'link', 'source', 'NER' (optional)
        """
        count = 0
        for r in recipes_data:
            # Basic validation
            if not r.get("title") or not r.get("ingredients"):
                continue

            # Create Recipe object
            recipe = Recipe(
                name=r.get("name"),
                ingredients_json=json.dumps(r.get("ingredients", [])),
                instructions_json=json.dumps(r.get("instructions", [])),
                allergens_json=json.dumps(r.get("allergens", [])),
                nutrition_json=json.dumps(r.get("nutrition", {})),
                source_url=r.get("link", ""),
                # Kaggle dataset might not have these, assume generic defaults or None
                cuisine=None,
                category=None,
                meal_type=None,
                prep_time_minutes=None
            )

            self.session.add(recipe)
            self.session.flush() # Get ID

            # Create Ingredients for matching
            # Prefer NER (Named Entity Recognition) column if available as it's cleaner
            # Otherwise use the raw ingredient strings
            ingredients_source = r.get("NER", r.get("ingredients", []))

            for ing_name in ingredients_source:
                # Normalize: lowercase
                clean_name = ing_name.lower().strip()
                if clean_name:
                    db_ing = RecipeIngredient(
                        recipe_id=recipe.id,
                        name=clean_name,
                        original_text=ing_name
                    )
                    self.session.add(db_ing)

            count += 1
            if count % 100 == 0:
                self.session.commit()
                logger.info(f"Imported {count} recipes...")

        self.session.commit()
        logger.info(f"Finished importing {count} recipes.")

def import_from_file(filepath: str, session: Session):
    with open(filepath, 'r') as f:
        # The Kaggle dataset can be a CSV or JSON.
        # If it's the "full_format_recipes.json" it might be a list of objects
        data = json.load(f)
        importer = RecipeImporter(session)
        importer.import_recipes(data)

if __name__ == "__main__":
    # Standalone run
    from sqlalchemy import create_engine

    # Use config setting
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
    with Session(engine) as session:
        import_from_file("backend/app/data/sample_kaggle_recipes.json", session)
