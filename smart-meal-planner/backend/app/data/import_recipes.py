"""
Local Bulk Recipe Importer & Validator CLI Tool.
Ingests structured recipe datasets (JSON, JSON-LD, Schema.org, open recipe corpora),
validates them against schemas.RecipeIngestion, and merges cleanly into
app/data/recipes.json and the local SQLite database.
"""

import json
import logging
import argparse
import os
import sys
from typing import List, Dict, Any, Tuple, Optional
from sqlmodel import Session, select
from sqlalchemy import create_engine

# Ensure app is in path when run standalone
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, "../.."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.models.all_models import Recipe, RecipeIngredient
from app.schemas import RecipeIngestion
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class RecipeImporter:
    def __init__(self, session: Session = None):
        self.session = session

    @staticmethod
    def validate_recipe(data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[RecipeIngestion]]:
        """Validates a raw recipe dictionary against RecipeIngestion schema."""
        try:
            # Handle Schema.org / JSON-LD format mappings
            mapped = dict(data)
            if "recipeIngredient" in mapped and "ingredients" not in mapped:
                mapped["ingredients"] = [{"item": i, "quantity": 1, "unit": "unit"} for i in mapped["recipeIngredient"]]
            if "recipeInstructions" in mapped and "instructions" not in mapped:
                insts = mapped["recipeInstructions"]
                if isinstance(insts, list):
                    mapped["instructions"] = [i.get("text", str(i)) if isinstance(i, dict) else str(i) for i in insts]
                elif isinstance(insts, str):
                    mapped["instructions"] = [insts]

            validated = RecipeIngestion(**mapped)
            return True, None, validated
        except Exception as e:
            return False, str(e), None

    def import_recipes(self, recipes_data: List[Dict[str, Any]], merge_json: bool = False) -> int:
        """
        Imports and validates a list of recipes into the database and optionally merges with recipes.json.
        """
        count = 0
        valid_records = []
        recipes_json_path = os.path.join(current_dir, "recipes.json")

        for r in recipes_data:
            is_valid, err, val_recipe = self.validate_recipe(r)
            if not is_valid or not val_recipe:
                logger.debug(f"Skipping invalid recipe: {err}")
                continue

            valid_records.append(val_recipe.model_dump())

            if self.session:
                # Check for existing recipe by name
                existing = self.session.exec(select(Recipe).where(Recipe.name == val_recipe.name)).first()
                if existing:
                    continue

                recipe = Recipe(
                    name=val_recipe.name,
                    ingredients_json=json.dumps(val_recipe.ingredients),
                    instructions_json=json.dumps(val_recipe.instructions or []),
                    allergens_json=json.dumps(val_recipe.allergens or []),
                    nutrition_json=json.dumps(val_recipe.nutrition or {}),
                    cuisine=val_recipe.cuisine,
                    meal_type=val_recipe.meal_type,
                    prep_time_minutes=val_recipe.prep_time_minutes,
                    difficulty=val_recipe.difficulty,
                    servings=val_recipe.servings,
                    dietary_tags_json=json.dumps(val_recipe.dietary_tags or []),
                )
                self.session.add(recipe)
                self.session.flush()

                for ing in val_recipe.ingredients:
                    ing_name = ing.get("item") if isinstance(ing, dict) else str(ing)
                    clean_name = ing_name.lower().strip() if ing_name else ""
                    if clean_name:
                        db_ing = RecipeIngredient(
                            recipe_id=recipe.id,
                            name=clean_name,
                            original_text=str(ing)
                        )
                        self.session.add(db_ing)

                count += 1
                if count % 50 == 0:
                    self.session.commit()
                    logger.info(f"Imported {count} recipes into SQLite...")

        if self.session:
            self.session.commit()
            logger.info(f"Successfully committed {count} recipes to database.")

        if merge_json and os.path.exists(recipes_json_path):
            with open(recipes_json_path, "r", encoding="utf-8") as f:
                current_recipes = json.load(f)
            current_names = {r["name"].lower() for r in current_recipes}
            added = 0
            for vr in valid_records:
                if vr["name"].lower() not in current_names:
                    current_recipes.append(vr)
                    current_names.add(vr["name"].lower())
                    added += 1
            with open(recipes_json_path, "w", encoding="utf-8") as f:
                json.dump(current_recipes, f, ensure_ascii=False, indent=2)
            logger.info(f"Merged {added} new recipes into recipes.json (Total now: {len(current_recipes)}).")

        return count


def main():
    parser = argparse.ArgumentParser(description="Local Bulk Recipe Importer & Validator CLI")
    parser.add_argument("--file", "-f", help="Path to JSON/JSON-LD file to import", default=None)
    parser.add_argument("--sync-sqlite", action="store_true", help="Sync all recipes from recipes.json into SQLite")
    parser.add_argument("--validate-only", action="store_true", help="Validate recipes without writing to DB")
    parser.add_argument("--merge-json", action="store_true", help="Merge valid recipes into recipes.json")
    parser.add_argument("--count", action="store_true", help="Show total recipe count in recipes.json and SQLite")

    args = parser.parse_args()
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)

    recipes_json_path = os.path.join(current_dir, "recipes.json")

    if args.count:
        if os.path.exists(recipes_json_path):
            with open(recipes_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"📊 Total recipes in recipes.json: {len(data)}")
        with Session(engine) as session:
            db_count = session.exec(select(Recipe)).all()
            print(f"📊 Total recipes in SQLite: {len(db_count)}")
        return

    if args.sync_sqlite:
        with open(recipes_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        with Session(engine) as session:
            importer = RecipeImporter(session)
            imported = importer.import_recipes(data)
            print(f"✅ Synced {imported} recipes into SQLite. Total DB records: {len(session.exec(select(Recipe)).all())}")
        return

    if args.file:
        if not os.path.exists(args.file):
            print(f"❌ File not found: {args.file}")
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            data = [data]

        if args.validate_only:
            valid_count = 0
            for idx, r in enumerate(data):
                ok, err, _ = RecipeImporter.validate_recipe(r)
                if ok:
                    valid_count += 1
                else:
                    print(f"Recipe #{idx} Invalid: {err}")
            print(f"Validation summary: {valid_count}/{len(data)} recipes valid.")
            return

        with Session(engine) as session:
            importer = RecipeImporter(session)
            imported = importer.import_recipes(data, merge_json=args.merge_json)
            print(f"Successfully processed and imported {imported} recipes.")
    else:
        # Default run: sync recipes.json
        print("No file specified. Use --sync-sqlite to sync recipes.json into SQLite, or --file <path> to import.")


if __name__ == "__main__":
    main()
