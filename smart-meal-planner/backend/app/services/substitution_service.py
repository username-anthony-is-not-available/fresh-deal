import json
from typing import Dict, List, Optional

class SubstitutionService:
    _substitutions: Optional[Dict[str, List[str]]] = None

    def __init__(self, filepath: str = "app/data/substitutions.json"):
        self.filepath = filepath

    def _load_substitutions(self) -> Dict[str, List[str]]:
        if self._substitutions is None:
            try:
                with open(self.filepath) as f:
                    self._substitutions = json.load(f)
            except FileNotFoundError:
                self._substitutions = {}
        return self._substitutions

    def get_substitutions(self, ingredients: List[str]) -> Dict[str, List[str]]:
        substitutions = self._load_substitutions()
        return {
            ingredient: substitutions[ingredient]
            for ingredient in ingredients
            if ingredient in substitutions
        }

substitution_service = SubstitutionService()
