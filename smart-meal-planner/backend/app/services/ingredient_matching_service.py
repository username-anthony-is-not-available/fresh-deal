
import re
import json
import os
import logging
from typing import List, Dict, Optional, Tuple
from thefuzz import fuzz

logger = logging.getLogger(__name__)

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
            "natural", "original", "premium", "quality"
        ]

    def _load_substitutions(self, path: str) -> Dict[str, List[str]]:
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading substitutions: {e}")
            return {}

    def normalize(self, text: str) -> str:
        if not text:
            return ""

        # Lowercase
        text = text.lower()

        # Remove numbers followed by units or just standalone numbers (like 1kg, 500g)
        # But be careful with things like "2% milk" (maybe keep % for now)
        text = re.sub(r"\d+\s*(?:kg|lb|g|ml|l|oz|gram|kilo|pound|litre|liter|milliliter|millilitre)\b", " ", text)
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

    def is_match(self, item1: str, item2: str, threshold: int = 80) -> bool:
        """
        Check if two ingredient/product strings match.
        """
        norm1 = self.normalize(item1)
        norm2 = self.normalize(item2)

        if not norm1 or not norm2:
            return False

        # 1. Exact match
        if norm1 == norm2:
            return True

        # 2. Substring match
        if norm1 in norm2 or norm2 in norm1:
            return True

        # 3. Fuzzy match (token_set_ratio handles different word orders and extra words)
        score = fuzz.token_set_ratio(norm1, norm2)
        if score >= threshold:
            return True

        # 4. Synonym/Substitution match
        # If item1 is "butter" and item2 is "margarine", and they are in substitutions
        for primary, syns in self.substitutions.items():
            primary_norm = self.normalize(primary)
            syns_norm = [self.normalize(s) for s in syns]

            if (norm1 == primary_norm and norm2 in syns_norm) or \
               (norm2 == primary_norm and norm1 in syns_norm):
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
        if not norm_target:
            return None

        # We'll use process.extractOne with a custom score if needed,
        # but thefuzz's default should be okay if we pre-normalize.

        # However, to maintain consistency with is_match, let's do it manually
        # or ensure normalization is used.

        best_score = -1
        best_candidate = None

        for cand in candidates:
            norm_cand = self.normalize(cand)
            if not norm_cand:
                continue

            # Use token_set_ratio for robustness
            score = fuzz.token_set_ratio(norm_target, norm_cand)

            # Check for substring match bonus
            if norm_target in norm_cand or norm_cand in norm_target:
                score = max(score, 95) # High score for substrings

            if score > best_score:
                best_score = score
                best_candidate = cand

        if best_score >= threshold:
            return best_candidate, best_score

        return None

# Singleton instance
ingredient_matching_service = IngredientMatchingService()
