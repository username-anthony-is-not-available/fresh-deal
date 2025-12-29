
import json
import logging
import redis
import hashlib
import json
import logging
import redis
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from openai import OpenAI, APIError, RateLimitError, APITimeoutError, APIConnectionError, InternalServerError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
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

    def format_deals_for_llm(self, deals: List[Dict]) -> str:
        """
        Convert deals to LLM-friendly format with context.
        """
        formatted = []
        for deal in deals:
            formatted.append({
                "product": deal.get("product"),
                "store": deal.get("store"),
                "category": deal.get("category", "general"),
                "sale_price": deal.get("price"),
                "regular_price": deal.get("regular_price", (deal.get("price") or 0) * 1.5),
                "discount_percent": deal.get("discount", 0),
                "expires_in_days": deal.get("expires_in_days", 7),
                "unit": deal.get("unit", "each")
            })

        # Sort by discount % to highlight best deals
        formatted.sort(key=lambda x: x["discount_percent"], reverse=True)

        return json.dumps(formatted[:30], indent=2)  # Top 30 deals only to save tokens

    def get_next_week_dates(self) -> List[Dict]:
        """
        Returns dates for the upcoming Monday-Sunday.
        """
        today = datetime.now()
        # Find next Monday
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7  # If today is Monday, start next Monday

        start_date = today + timedelta(days=days_until_monday)

        dates = []
        for i in range(7):
            date = start_date + timedelta(days=i)
            dates.append({
                "day": i + 1,
                "day_name": date.strftime("%A"),
                "date": date.strftime("%Y-%m-%d"),
                "display_date": date.strftime("%b %d")  # "Dec 09"
            })

        return dates

    def generate_meal_plan(self, user_prefs: Dict, available_deals: List[Dict], recipes_db: List[Dict], user_favorites: List[int] = None) -> Dict:
        """
        Generates a meal plan based on user preferences and available deals.

        Args:
            user_prefs: User preferences (household size, etc.)
            available_deals: List of current deals
            recipes_db: List of recipes, potentially with 'average_rating'
            user_favorites: List of favorite recipe IDs
        """
        user_favorites = user_favorites or []
        week_dates = self.get_next_week_dates()

        # Create a cache key.
        cache_key_data = {
            "prefs": user_prefs,
            "deals": available_deals[:20],
            "week": week_dates[0]['date'],
            "favorites": sorted(user_favorites)
        }
        cache_key = self._get_cache_key("meal_plan", cache_key_data)
        cached = self._get_cached_response(cache_key)
        if cached:
            logger.info("Returning cached meal plan")
            return cached

        prompt = self._construct_meal_plan_prompt(user_prefs, available_deals, recipes_db, week_dates, user_favorites)

        try:
            response = self._call_llm(prompt)
            plan = self._parse_llm_response(response)
            self._set_cached_response(cache_key, plan)
            return plan
        except Exception as e:
            logger.error(f"LLM generation failed: {e}. Falling back to mock data.")
            return self._generate_mock_plan(user_prefs, recipes_db, week_dates)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)),
        before_sleep=lambda retry_state: logger.warning(f"Retrying LLM call due to {retry_state.outcome.exception()}...")
    )
    def _make_api_request(self, model: str, prompt: str) -> str:
        """Makes a single, retriable API call to the LLM."""
        completion = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful meal planning assistant that outputs valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            timeout=120,
        )
        content = completion.choices[0].message.content
        if not content:
            raise ValueError(f"Empty response from LLM model {model}")
        return content

    def _call_llm(self, prompt: str) -> str:
        """
        Calls the LLM API, handling mock mode, primary/fallback models, and retries.
        """
        if settings.USE_MOCK_AI or not settings.OPENROUTER_API_KEY:
            logger.info("Mock AI enabled or API Key missing. Triggering fallback.")
            raise APIError("Mock AI enabled or API Key missing", request=None, body=None)

        # Try primary model
        try:
            logger.info(f"Calling primary LLM model: {self.model}")
            return self._make_api_request(self.model, prompt)
        except Exception as e:
            logger.warning(f"Primary LLM model '{self.model}' failed after retries: {e}")

        # Try fallback model
        try:
            logger.info(f"Calling fallback LLM model: {self.fallback_model}")
            return self._make_api_request(self.fallback_model, prompt)
        except Exception as e2:
            logger.error(f"Fallback LLM model '{self.fallback_model}' also failed after retries: {e2}")
            raise APIError(f"Both primary and fallback LLM models failed.", request=None, body=None)

    def _construct_meal_plan_prompt(self, user_prefs: Dict, deals: List[Dict], recipes: List[Dict], week_dates: List[Dict], user_favorites: List[int]) -> str:
        formatted_deals = self.format_deals_for_llm(deals)
        household_size = user_prefs.get('household_size', 1)

        return f"""
        Create a 7-day meal plan (Breakfast, Lunch, Dinner) for a user with these preferences: {json.dumps(user_prefs)}.

        GENERATE PLAN FOR: {week_dates[0]['date']} to {week_dates[6]['date']}

        USER CONTEXT:
        - Household: {household_size} people. Scale recipe ingredients and shopping quantities accordingly.
        - Nutritional Goals: Aim for a daily average of {user_prefs.get('target_calories', 2000)} calories and {user_prefs.get('target_fiber', 30)}g of fiber.
        - Allergies to Avoid: {json.dumps(user_prefs.get('allergies', []))}
        - Dietary Restrictions: {json.dumps(user_prefs.get('dietary_preferences', []))}

        USER'S FAVORITE RECIPES (HIGHEST PRIORITY):
        {json.dumps(user_favorites)}

        AVAILABLE DEALS (Expiring Soon):
        {formatted_deals}

        RECIPE SELECTION RULES:
        1. You MUST select 21 meals from the provided recipe list.
        2. PRIORITY RULES:
           - HIGHEST PRIORITY: Strongly prefer recipes from the user's favorites list.
           - HIGH PRIORITY: Prioritize recipes with a high average rating (4 stars or higher).
           - MEDIUM PRIORITY: Prioritize recipes that use ingredients currently on sale.
        3. GENERAL RULES:
           - Never repeat the same meal or protein source on consecutive days.
           - Space repeated meals at least 3 days apart.
           - Ensure variety in cuisines.
           - Respect dietary restrictions.

        AVAILABLE RECIPES (includes average ratings):
        {json.dumps(self._format_recipes_for_prompt(recipes))}

        RETURN JSON STRUCTURE:
        {{
          "meal_plan": [
            {{
              "day": 1,
              "day_name": "Monday",
              "date": "{week_dates[0]['date']}",
              "breakfast": {{
                "recipe_id": "recipe_001",
                "recipe_name": "Recipe Name",
                "reason": "Reason for selection (e.g., user favorite, high rating, uses sale items)",
                "servings": {household_size},
                "scaled_for_household": true
              }},
              "lunch": {{...}},
              "dinner": {{...}}
            }}
          ],
          "shopping_summary": {{
            "key_deals_used": ["item1", "item2"],
            "estimated_savings": 28.50,
            "nutritional_balance": "Balanced across macros",
            "household_size": {household_size}
          }},
          "weekly_overview": "This week focuses on..."
        }}
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

    def _format_recipes_for_prompt(self, recipes: List[Dict]) -> List[Dict]:
        """Formats recipes (both legacy dicts and new DB objects converted to dicts) for the prompt."""
        formatted = []
        for r in recipes:
            # Handle DB model dict conversion
            ingredients = r.get('ingredients', [])
            # If ingredients is a JSON string (new DB model), parse it
            if isinstance(ingredients, str):
                try:
                    ingredients = json.loads(ingredients)
                except:
                    ingredients = []
            # Legacy format check
            elif isinstance(ingredients, list) and len(ingredients) > 0 and isinstance(ingredients[0], dict):
                 ingredients = [i.get('item', '') for i in ingredients]

            nutrition = r.get('nutrition', {})
            allergens = r.get('allergens', [])
            if isinstance(allergens, str):
                try:
                    allergens = json.loads(allergens)
                except:
                    allergens = []

            dietary_tags = r.get('dietary_tags', [])
            if isinstance(dietary_tags, str):
                try:
                    dietary_tags = json.loads(dietary_tags)
                except:
                    dietary_tags = []

            formatted.append({
                'id': r.get('id'),
                'name': r.get('name'),
                'ingredients': ingredients,
                'meal_type': r.get('meal_type', 'Any'),
                'average_rating': r.get('average_rating'),
                'nutrition': {
                    'calories': nutrition.get('calories'),
                    'protein': nutrition.get('protein'),
                    'carbs': nutrition.get('carbs'),
                    'fat': nutrition.get('fat'),
                    'fiber': nutrition.get('fiber')
                },
                'allergens': allergens,
                'dietary_tags': dietary_tags
            })
        return formatted

    def _generate_mock_plan(self, user_prefs: Dict, recipes: List[Dict], week_dates: List[Dict]) -> Dict:
        """Fallback mock plan generation."""
        import random

        days = []
        for i, date_info in enumerate(week_dates):
            day_meals = {}
            for m_type in ["Breakfast", "Lunch", "Dinner"]:
                # Filter by meal type if available in recipe
                candidates = [r for r in recipes if str(r.get("meal_type")).lower() == m_type.lower() or r.get("meal_type") == 'Any']
                if not candidates:
                    candidates = recipes

                if candidates:
                    recipe = random.choice(candidates)
                    day_meals[m_type.lower()] = {
                        "recipe_id": recipe.get("id"),
                        "recipe_name": recipe.get("name", "Unknown Meal"),
                        "reason": "Mock fallback selection",
                        "servings": user_prefs.get('household_size', 1),
                        "scaled_for_household": True
                    }

            days.append({
                "day": i + 1,
                "day_name": date_info['day_name'],
                "date": date_info['date'],
                "breakfast": day_meals.get('breakfast'),
                "lunch": day_meals.get('lunch'),
                "dinner": day_meals.get('dinner')
            })

        return {
            "meal_plan": days,
            "shopping_summary": {
                "key_deals_used": ["Mock Deal 1", "Mock Deal 2"],
                "estimated_savings": 10.00,
                "nutritional_balance": "Mock Balance",
                "household_size": user_prefs.get('household_size', 1)
            },
            "weekly_overview": "This is a mock plan generated because the AI service was unavailable."
        }
