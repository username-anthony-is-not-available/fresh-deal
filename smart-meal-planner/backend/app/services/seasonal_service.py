import json
import os
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class SeasonalService:
    def __init__(self):
        self.seasonal_data = self._load_seasonal_data()

    def _load_seasonal_data(self) -> Dict[str, List[str]]:
        """Loads the seasonal calendar from the JSON file."""
        file_path = os.path.join(os.path.dirname(__file__), "..", "data", "seasonal_calendar.json")
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading seasonal data: {e}")
            return {}

    def get_seasonal_ingredients(self, month: int) -> List[str]:
        """Returns the list of seasonal ingredients for a given month (1-12)."""
        return self.seasonal_data.get(str(month), [])

    def calculate_seasonal_score(self, ingredients: List[str], month: int) -> float:
        """
        Calculates a seasonal score based on how many ingredients are in season.
        Each seasonal ingredient adds 0.5 to the score.
        """
        seasonal_items = [item.lower() for item in self.get_seasonal_ingredients(month)]
        if not seasonal_items:
            return 0.0

        score = 0.0
        for ing in ingredients:
            ing_lower = ing.lower()
            # Simple check: if any seasonal item is part of the ingredient name
            for item in seasonal_items:
                if item in ing_lower:
                    score += 0.5
                    break
        return round(score, 2)
