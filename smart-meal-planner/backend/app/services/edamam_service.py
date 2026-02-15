import httpx
from typing import Dict, Any, List

class EdamamService:
    def __init__(self, app_id: str, app_key: str):
        self.app_id = app_id
        self.app_key = app_key
        self.base_url = "https://api.edamam.com/api/nutrition-details"

    async def get_nutrition_data(self, title: str, ingredients: List[str]) -> Dict[str, Any]:
        """
        Fetches nutritional data for a list of ingredients using Edamam Nutrition Analysis API.
        """
        if not self.app_id or not self.app_key:
            return {}

        payload = {
            "title": title,
            "ingr": ingredients
        }
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.base_url, json=payload, params=params)
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_response(data)
                else:
                    return {}
            except Exception:
                return {}

    def _parse_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses Edamam response into a simplified nutrition dictionary.
        """
        nutrients = data.get("totalNutrients", {})
        return {
            "calories": int(data.get("calories", 0)),
            "protein": int(nutrients.get("PROCNT", {}).get("quantity", 0)),
            "carbs": int(nutrients.get("CHOCDF", {}).get("quantity", 0)),
            "fat": int(nutrients.get("FAT", {}).get("quantity", 0)),
            "fiber": int(nutrients.get("FIBTG", {}).get("quantity", 0)),
        }
