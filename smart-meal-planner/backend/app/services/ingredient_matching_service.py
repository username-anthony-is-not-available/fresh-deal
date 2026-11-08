import re
import json
import os
import logging
from typing import List, Dict, Optional, Tuple, Any

try:
    from rapidfuzz import fuzz
except ImportError:
    from thefuzz import fuzz  # pragma: no cover

logger = logging.getLogger(__name__)


# Deterministic density lookup (grams per ml) for volume-to-weight conversions
INGREDIENT_DENSITY_TABLE: Dict[str, float] = {
    "water": 1.0,
    "milk": 1.03,
    "cream": 1.01,
    "oil": 0.92,
    "olive oil": 0.92,
    "canola oil": 0.92,
    "butter": 0.96,
    "flour": 0.53,
    "sugar": 0.85,
    "brown sugar": 0.80,
    "rice": 0.85,
    "oats": 0.40,
    "honey": 1.42,
    "maple syrup": 1.33,
    "yogurt": 1.06,
    "broth": 1.0,
    "chicken broth": 1.0,
    "beef broth": 1.0,
    "sauce": 1.05,
    "tomato sauce": 1.05,
    "default": 1.0,
}

# Standard metric / imperial mass and volume conversions to canonical base units (grams for weight, ml for volume)
MASS_TO_GRAMS: Dict[str, float] = {
    "g": 1.0,
    "gram": 1.0,
    "grams": 1.0,
    "gramme": 1.0,
    "grammes": 1.0,
    "kg": 1000.0,
    "kilo": 1000.0,
    "kilogram": 1000.0,
    "kilograms": 1000.0,
    "kilogramme": 1000.0,
    "kilogrammes": 1000.0,
    "100g": 100.0,
    "lb": 453.59237,
    "lbs": 453.59237,
    "pound": 453.59237,
    "pounds": 453.59237,
    "livre": 453.59237,
    "livres": 453.59237,
    "oz": 28.3495,
    "ounce": 28.3495,
    "ounces": 28.3495,
}

VOLUME_TO_ML: Dict[str, float] = {
    "ml": 1.0,
    "milliliter": 1.0,
    "milliliters": 1.0,
    "millilitre": 1.0,
    "millilitres": 1.0,
    "l": 1000.0,
    "liter": 1000.0,
    "liters": 1000.0,
    "litre": 1000.0,
    "litres": 1000.0,
    "cup": 240.0,
    "cups": 240.0,
    "tasse": 240.0,
    "tasses": 240.0,
    "tbsp": 15.0,
    "tablespoon": 15.0,
    "tablespoons": 15.0,
    "c. à soupe": 15.0,
    "c. a soupe": 15.0,
    "tsp": 5.0,
    "teaspoon": 5.0,
    "teaspoons": 5.0,
    "c. à thé": 5.0,
    "c. a the": 5.0,
    "fl oz": 29.5735,
}

# Bilingual canonical ingredient dictionary (Quebec French <-> English)
BILINGUAL_CANONICAL_MAP: Dict[str, str] = {
    # Poultry
    "poitrine de poulet désossée": "chicken breast",
    "poitrine de poulet": "chicken breast",
    "poulet désossé": "chicken breast",
    "boneless skinless chicken breast": "chicken breast",
    "boneless chicken breast": "chicken breast",
    "hauts de cuisse de poulet": "chicken thighs",
    "cuisses de poulet": "chicken thighs",
    "pilons de poulet": "chicken drumsticks",
    "poulet entier": "whole chicken",
    "dindon": "turkey",
    "dinde": "turkey",
    # Beef & Pork
    "boeuf haché mi-maigre": "ground beef",
    "boeuf haché maigre": "ground beef",
    "boeuf haché": "ground beef",
    "medium ground beef": "ground beef",
    "lean ground beef": "ground beef",
    "rôti de boeuf": "beef roast",
    "steak de boeuf": "beef steak",
    "bifteck": "beef steak",
    "filet de porc": "pork tenderloin",
    "longe de porc": "pork loin",
    "côtelettes de porc": "pork chops",
    "porc haché": "ground pork",
    "bacon": "bacon",
    "jambon": "ham",
    "saucisses": "sausages",
    # Fish & Seafood
    "saumon de l'atlantique": "salmon",
    "filet de saumon": "salmon",
    "saumon": "salmon",
    "truite": "trout",
    "crevettes": "shrimp",
    "morue": "cod",
    "thon": "tuna",
    # Produce
    "pommes de terre": "potatoes",
    "patates": "potatoes",
    "carottes": "carrots",
    "oignons": "onions",
    "oignons jaunes": "onions",
    "oignons rouges": "red onions",
    "ail": "garlic",
    "brocoli": "broccoli",
    "chou-fleur": "cauliflower",
    "courgette": "zucchini",
    "poivrons": "bell peppers",
    "poivrons doux": "bell peppers",
    "poivron rouge": "bell peppers",
    "épinards": "spinach",
    "laitue": "lettuce",
    "laitue romaine": "lettuce",
    "tomates": "tomatoes",
    "tomates en grappe": "tomatoes",
    "champignons": "mushrooms",
    "pommes": "apples",
    "pommes gala": "apples",
    "pommes honeycrisp": "apples",
    "pommes mcintosh": "apples",
    "bananes": "bananas",
    "oranges": "oranges",
    "citrons": "lemons",
    "avocats": "avocados",
    # Dairy & Eggs
    "lait": "milk",
    "lait 2%": "milk",
    "lait entier": "milk",
    "oeufs": "eggs",
    "oeufs gros": "eggs",
    "beurre": "butter",
    "beurre salé": "butter",
    "beurre non salé": "butter",
    "fromage cheddar": "cheddar cheese",
    "fromage p'tit québec": "cheddar cheese",
    "fromage râpé": "shredded cheese",
    "fromage mozzarella": "mozzarella cheese",
    "fromage halloumi": "halloumi",
    "halloumi": "halloumi",
    "crème sure": "sour cream",
    "yogourt": "yogurt",
    "yogourt grec": "greek yogurt",
    # Pantry & Bakery
    "riz": "rice",
    "riz blanc": "rice",
    "riz basmati": "rice",
    "riz brun": "brown rice",
    "pâtes": "pasta",
    "pâtes alimentaires": "pasta",
    "spaghetti": "pasta",
    "macaroni": "pasta",
    "pain": "bread",
    "pain tranché": "bread",
    "farine": "flour",
    "sucre": "sugar",
    "huile d'olive": "olive oil",
    "huile de canola": "canola oil",
    "huile végétale": "vegetable oil",
    "sauce tomate": "tomato sauce",
    "bouillon de poulet": "chicken broth",
    "bouillon de boeuf": "beef broth",
    "haricots noirs": "black beans",
    "pois chiches": "chickpeas",
    "lentilles": "lentils",
}


class IngredientMatchingService:
    def __init__(self, substitutions_path: str = None):
        if substitutions_path is None:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            substitutions_path = os.path.join(base_path, "data", "substitutions.json")

        self.substitutions = self._load_substitutions(substitutions_path)
        self.common_units = [
            r"\bkg\b", r"\blb\b", r"\bg\b", r"\bml\b", r"\bl\b", r"\boz\b",
            r"\bgram(?:me)?s?\b", r"\bkilo(?:gram(?:me)?s?)?\b", r"\bpounds?\b",
            r"\blitre?s?\b", r"\bmillilitre?s?\b"
        ]
        self.filler_words = [
            "fresh", "organic", "frozen", "large", "small", "medium", "extra",
            "natural", "original", "premium", "quality", "frais", "fraiche",
            "biologique", "bio", "gros", "moyen", "petit", "naturel"
        ]
        self.density_table = INGREDIENT_DENSITY_TABLE
        self.bilingual_map = {self.normalize(k): self.normalize(v) for k, v in BILINGUAL_CANONICAL_MAP.items()}

    def _load_substitutions(self, path: str) -> Dict[str, List[str]]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading substitutions: {e}")
            return {}

    def normalize(self, text: str) -> str:
        if not text:
            return ""

        text = text.lower()

        # Remove percentages like 2% or 1%
        text = re.sub(r"\b\d+%\s*", "", text)

        # Remove numbers followed by units
        text = re.sub(r"\d+\s*(?:kg|lb|lbs|g|ml|l|oz|gram|kilo|pound|litre|liter|milliliter|millilitre)\b", " ", text)
        text = re.sub(r"\b\d+\b", " ", text)

        # Remove common units
        for unit in self.common_units:
            text = re.sub(unit, " ", text)

        # Remove filler words
        for filler in self.filler_words:
            text = re.sub(rf"\b{filler}\b", " ", text)

        # Remove punctuation
        text = re.sub(r"[^\w\s]", " ", text)

        # Collapse whitespace
        text = " ".join(text.split())
        return text

    def canonicalize(self, text: str) -> str:
        """
        Maps French and bilingual product phrasing to canonical ingredient name.
        """
        norm = self.normalize(text)
        if norm in self.bilingual_map:
            return self.bilingual_map[norm]

        for fr_key, canonical in self.bilingual_map.items():
            if fr_key in norm or norm in fr_key:
                return canonical

        return norm

    def is_match(self, item1: str, item2: str, threshold: int = 80) -> bool:
        """
        Check if two ingredient/product strings match using bilingual dictionary,
        exact, substring, token_set_ratio, and substitutions.
        """
        norm1 = self.normalize(item1)
        norm2 = self.normalize(item2)

        if not norm1 or not norm2:
            return False

        # 1. Exact match
        if norm1 == norm2:
            return True

        # 2. Canonical bilingual match
        canon1 = self.canonicalize(item1)
        canon2 = self.canonicalize(item2)
        if canon1 and canon2 and canon1 == canon2:
            return True

        # 3. Substring match
        if norm1 in norm2 or norm2 in norm1:
            return True

        # 4. Fuzzy match (rapidfuzz token_set_ratio)
        score = fuzz.token_set_ratio(norm1, norm2)
        if score >= threshold:
            return True

        canon_score = fuzz.token_set_ratio(canon1, canon2)
        if canon_score >= threshold:
            return True

        # 5. Synonym/Substitution match
        for primary, syns in self.substitutions.items():
            primary_norm = self.normalize(primary)
            syns_norm = [self.normalize(s) for s in syns]

            if (norm1 == primary_norm and norm2 in syns_norm) or \
               (norm2 == primary_norm and norm1 in syns_norm) or \
               (canon1 == primary_norm and canon2 in syns_norm) or \
               (canon2 == primary_norm and canon1 in syns_norm):
                return True

        return False

    def find_best_match(self, target: str, candidates: List[str], threshold: int = 70) -> Optional[Tuple[str, int]]:
        """
        Find the best match for a target string from a list of candidates.
        Returns (best_candidate, score) or None.
        """
        if not candidates:
            return None

        norm_target = self.normalize(target)
        canon_target = self.canonicalize(target)
        if not norm_target:
            return None

        best_score = -1
        best_candidate = None

        for cand in candidates:
            norm_cand = self.normalize(cand)
            canon_cand = self.canonicalize(cand)
            if not norm_cand:
                continue

            score = int(fuzz.token_set_ratio(norm_target, norm_cand))
            canon_score = int(fuzz.token_set_ratio(canon_target, canon_cand))
            score = max(score, canon_score)

            if norm_target in norm_cand or norm_cand in norm_target:
                score = max(score, 95)
            if canon_target == canon_cand and canon_target != "":
                score = max(score, 98)

            if score > best_score:
                best_score = score
                best_candidate = cand

        if best_score >= threshold:
            return best_candidate, best_score

        return None

    # Deterministic unit conversion logic
    def convert_quantity(
        self, quantity: float, from_unit: str, to_unit: str, ingredient_name: str = ""
    ) -> Tuple[float, bool]:
        """
        Converts quantity between metric and imperial units.
        Handles mass-to-mass, volume-to-volume, and density-assisted mass-to-volume.
        Returns (converted_quantity, is_exact).
        """
        f_unit = from_unit.strip().lower()
        t_unit = to_unit.strip().lower()

        if f_unit == t_unit:
            return quantity, True

        # Mass to mass
        if f_unit in MASS_TO_GRAMS and t_unit in MASS_TO_GRAMS:
            grams = quantity * MASS_TO_GRAMS[f_unit]
            res = grams / MASS_TO_GRAMS[t_unit]
            return round(res, 4), True

        # Volume to volume
        if f_unit in VOLUME_TO_ML and t_unit in VOLUME_TO_ML:
            ml = quantity * VOLUME_TO_ML[f_unit]
            res = ml / VOLUME_TO_ML[t_unit]
            return round(res, 4), True

        # Mass <-> Volume using density table
        density = self.density_table.get("default", 1.0)
        norm_name = self.normalize(ingredient_name)
        for ing_key, d in self.density_table.items():
            if ing_key in norm_name:
                density = d
                break

        # Mass -> Volume: volume_ml = grams / density
        if f_unit in MASS_TO_GRAMS and t_unit in VOLUME_TO_ML:
            grams = quantity * MASS_TO_GRAMS[f_unit]
            ml = grams / density
            res = ml / VOLUME_TO_ML[t_unit]
            return round(res, 4), False

        # Volume -> Mass: grams = volume_ml * density
        if f_unit in VOLUME_TO_ML and t_unit in MASS_TO_GRAMS:
            ml = quantity * VOLUME_TO_ML[f_unit]
            grams = ml * density
            res = grams / MASS_TO_GRAMS[t_unit]
            return round(res, 4), False

        # Fallback 1:1 if unit is unknown (e.g., 'each', 'can', 'pack')
        return quantity, False

    def calculate_cost(
        self, price: float, price_unit: str, required_qty: float, required_unit: str, ingredient_name: str = ""
    ) -> float:
        """
        Calculates exact ingredient cost based on flyer price and recipe required quantity.
        """
        converted_qty, _ = self.convert_quantity(required_qty, required_unit, price_unit, ingredient_name)
        cost = price * converted_qty
        return max(0.01, round(cost, 2))


# Singleton instance
ingredient_matching_service = IngredientMatchingService()
