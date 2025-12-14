import httpx
from typing import Dict, Any

class FatSecretService:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://platform.fatsecret.com/rest/server.api"

    async def search_food(self, food_item: str) -> Dict[str, Any]:
        """
        Searches for a food item using the FatSecret API.
        """
        params = {
            "method": "foods.search",
            "search_expression": food_item,
            "format": "json",
            "oauth_consumer_key": self.api_key,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": "...",
            "oauth_nonce": "...",
            "oauth_version": "1.0",
            "oauth_signature": "...",
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
            return response.json()

    async def get_food_details(self, food_id: int) -> Dict[str, Any]:
        """
        Gets detailed nutritional information for a specific food ID.
        """
        params = {
            "method": "food.get",
            "food_id": food_id,
            "format": "json",
            "oauth_consumer_key": self.api_key,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": "...",
            "oauth_nonce": "...",
            "oauth_version": "1.0",
            "oauth_signature": "...",
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
            return response.json()
