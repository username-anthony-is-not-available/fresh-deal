
import json
import logging
import redis
import hashlib
from typing import List, Dict, Any, Optional
from openai import OpenAI, APIError
from app.core.config import settings

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        # OpenAI client requires an API key. If not set, use a dummy one to avoid init crash.
        # We check for the real key in _call_llm before making requests.
        api_key = settings.OPENROUTER_API_KEY or "dummy_key"

        self.client = OpenAI(
            base_url=settings.OPENROUTER_BASE_URL,
            api_key=api_key
        )
        self.model = settings.DEFAULT_MODEL
        self.fallback_model = settings.FALLBACK_MODEL

        # Initialize Redis
        try:
            self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            # Test connection
            self.redis_client.ping()
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Caching disabled.")
            self.redis_client = None

    def _get_cache_key(self, prefix: str, data: Any) -> str:
        """Generates a cache key based on the input data."""
        data_str = json.dumps(data, sort_keys=True)
        hash_str = hashlib.md5(data_str.encode()).hexdigest()
        return f"{prefix}:{hash_str}"

    def _get_cached_response(self, key: str) -> Optional[Dict]:
        """Retrieves cached response if available."""
        if not self.redis_client:
            return None
        try:
            cached = self.redis_client.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
        return None

    def _set_cached_response(self, key: str, data: Any, ttl: int = 3600):
        """Stores response in cache."""
        if not self.redis_client:
            return
        try:
            self.redis_client.setex(key, ttl, json.dumps(data))
        except Exception as e:
            logger.error(f"Redis set error: {e}")

    def generate_meal_plan(self, user_prefs: Dict, available_deals: List[Dict], recipes_db: List[Dict]) -> Dict:
        """
        Generates a meal plan based on user preferences and available deals.
        """
        # Create a cache key. Limit deals to 20 to avoid huge keys, but ensure variety logic holds.
        cache_key = self._get_cache_key("meal_plan", {"prefs": user_prefs, "deals": available_deals[:20]})
        cached = self._get_cached_response(cache_key)
        if cached:
            logger.info("Returning cached meal plan")
            return cached

        prompt = self._construct_meal_plan_prompt(user_prefs, available_deals, recipes_db)

        try:
            response = self._call_llm(prompt)
            plan = self._parse_llm_response(response)
            self._set_cached_response(cache_key, plan)
            return plan
        except Exception as e:
            logger.error(f"LLM generation failed: {e}. Falling back to mock data.")
            return self._generate_mock_plan(user_prefs, recipes_db)

    def select_recipes(self, recipes: List[Dict], deals: List[Dict], preferences: Dict) -> List[Dict]:
        """
        Selects the best recipes from the database matching deals and preferences.
        """
        cache_key = self._get_cache_key("recipe_selection", {"recipes": len(recipes), "deals": len(deals), "prefs": preferences})
        cached = self._get_cached_response(cache_key)
        if cached:
            return cached

        prompt = self._construct_recipe_selection_prompt(recipes, deals, preferences)

        try:
            response = self._call_llm(prompt)
            parsed = self._parse_llm_response(response)

            # Expected format: {"selected_recipes": ["Name 1", "Name 2"]}
            selected_names = parsed.get("selected_recipes", [])

            # Match back to recipe objects
            selected_recipes = [r for r in recipes if r.get("name") in selected_names]

            if not selected_recipes:
                # If LLM returned empty or mismatched names, fallback or assume it meant indexes?
                # For now, simplistic fallback if empty.
                if len(selected_names) > 0:
                     logger.warning("LLM returned names but none matched db.")
                raise ValueError("No matching recipes found from LLM response")

            self._set_cached_response(cache_key, selected_recipes)
            return selected_recipes
        except Exception as e:
            logger.error(f"Recipe selection failed: {e}. Falling back to simple filtering.")
            return self._fallback_recipe_selection(recipes, preferences)

    def _call_llm(self, prompt: str) -> str:
        """Calls the LLM API."""
        if settings.USE_MOCK_AI or not settings.OPENROUTER_API_KEY:
            # We raise an error to trigger the fallback logic in the caller methods
            raise APIError("Mock AI enabled or API Key missing", request=None, body=None)

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful meal planning assistant that outputs valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            content = completion.choices[0].message.content
            if not content:
                 raise ValueError("Empty response from LLM")
            return content
        except Exception as e:
            logger.warning(f"Primary model failed: {e}. Trying fallback.")
            try:
                completion = self.client.chat.completions.create(
                    model=self.fallback_model,
                    messages=[
                        {"role": "system", "content": "You are a helpful meal planning assistant that outputs valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                content = completion.choices[0].message.content
                if not content:
                    raise ValueError("Empty response from LLM fallback")
                return content
            except Exception as e2:
                raise APIError(f"Both models failed: {e2}", request=None, body=None)

    def _construct_meal_plan_prompt(self, user_prefs: Dict, deals: List[Dict], recipes: List[Dict]) -> str:
        # Simplified prompt construction
        return f"""
        Create a 7-day meal plan (Breakfast, Lunch, Dinner) for a user with these preferences: {json.dumps(user_prefs)}.
        Consider these available deals: {json.dumps(deals[:20])}.
        Use these recipes if possible: {json.dumps([r['name'] for r in recipes[:50]])}.
        Return a JSON object with a 'days' array, where each day has 'day' number and 'meals' list.
        Each meal should have 'type', 'name', 'ingredients'.
        """

    def _construct_recipe_selection_prompt(self, recipes: List[Dict], deals: List[Dict], prefs: Dict) -> str:
        return f"""
        Select the top 5 recipes from the provided list that best match the user's preferences and maximize savings based on deals.
        User Preferences: {json.dumps(prefs)}
        Deals: {json.dumps(deals[:20])}
        Recipes: {json.dumps([{'id': r.get('id'), 'name': r.get('name'), 'tags': r.get('tags')} for r in recipes])}
        Return a JSON object with a key 'selected_recipes' containing a list of recipe names.
        """

    def _parse_llm_response(self, response: str) -> Any:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to find JSON block
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end != -1:
                return json.loads(response[start:end])
            raise ValueError("Could not parse JSON from LLM response")

    def _generate_mock_plan(self, user_prefs: Dict, recipes: List[Dict]) -> Dict:
        """Fallback mock plan generation (simplified version of planner_agent logic)."""
        import random
        days = []
        for i in range(1, 8):
            day_meals = []
            for m_type in ["Breakfast", "Lunch", "Dinner"]:
                # Filter by meal type if available in recipe
                candidates = [r for r in recipes if r.get("meal_type") == m_type]
                if not candidates:
                    candidates = recipes

                if candidates:
                    recipe = random.choice(candidates)
                    day_meals.append({
                        "type": m_type,
                        "name": recipe.get("name", "Unknown Meal"),
                        "ingredients": [ing["item"] for ing in recipe.get("ingredients", [])],
                        "id": recipe.get("id")
                    })
            days.append({"day": i, "meals": day_meals})

        return {
            "days": days,
            "shopping_list_summary": "Generated via Mock Fallback",
            "nutritional_summary": {"note": "Mock Data"}
        }

    def _fallback_recipe_selection(self, recipes: List[Dict], prefs: Dict) -> List[Dict]:
        """Simple filtering fallback."""
        filtered = recipes
        if prefs.get("vegetarian"):
            filtered = [r for r in filtered if "vegetarian" in r.get("tags", [])]
        return filtered[:5]
