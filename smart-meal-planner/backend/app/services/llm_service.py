
import json
import logging
import os
import sqlite3
import time
import redis
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from openai import OpenAI, APIError, RateLimitError, APITimeoutError, APIConnectionError, InternalServerError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.core.config import settings
from app.services.recipe_service import RecipeService
from app.services.deal_service import DealService
from app.services.seasonal_service import SeasonalService

logger = logging.getLogger(__name__)

class LLMService:
    MODEL_MAPPING = {
        "standard": settings.DEFAULT_MODEL,
        "chef": settings.OPENROUTER_MODEL,  # anthropic/claude-3.5-sonnet
        "creative": "google/gemini-pro-1.5",
        "budget": "meta-llama/llama-3.1-70b-instruct",
    }

    def _get_seasonal_context(self) -> str:
        """Returns typical Quebec ingredients for the current month."""
        month = datetime.now().month
        ingredients = self.seasonal_service.get_seasonal_ingredients(month)
        ingredients_str = ", ".join(ingredients)

        # Simple season name for context
        if 3 <= month <= 5:
            season = "Spring"
        elif 6 <= month <= 8:
            season = "Summer"
        elif 9 <= month <= 11:
            season = "Autumn"
        else:
            season = "Winter"

        return f"Current Month: {datetime.now().strftime('%B')}. Season in Quebec: {season}. Highly recommended local seasonal ingredients: {ingredients_str}."

    def __init__(self):
        # OpenAI client requires an API key. If not set, use a dummy one to avoid init crash.
        # We check for the real key in _call_llm before making requests.
        api_key = settings.OPENROUTER_API_KEY or "dummy_key"

        self.client = OpenAI(
            base_url=settings.OPENROUTER_BASE_URL,
            api_key=api_key
        )

        # Ollama / Local OpenAI-compatible client
        self.ollama_base_url = settings.OLLAMA_BASE_URL
        if self.ollama_base_url:
            self.ollama_client = OpenAI(
                base_url=self.ollama_base_url,
                api_key="ollama"
            )
        else:
            self.ollama_client = None

        self.model = settings.DEFAULT_MODEL
        self.fallback_model = settings.FALLBACK_MODEL
        self.seasonal_service = SeasonalService()

        # Initialize Redis
        try:
            self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            # Test connection
            self.redis_client.ping()
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Caching disabled.")
            self.redis_client = None

        # Initialize SQLite prompt cache for local offline execution
        self.sqlite_cache_dir = os.path.join(os.getcwd(), ".cache")
        try:
            os.makedirs(self.sqlite_cache_dir, exist_ok=True)
            self.sqlite_cache_path = os.path.join(self.sqlite_cache_dir, "llm_cache.sqlite")
            with sqlite3.connect(self.sqlite_cache_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS prompt_cache (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        expires_at REAL NOT NULL
                    )
                ''')
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to initialize SQLite LLM cache: {e}")
            self.sqlite_cache_path = None

    def _get_cache_key(self, prefix: str, data: Any) -> str:
        """Generates a cache key based on the input data."""
        data_str = json.dumps(data, sort_keys=True)
        hash_str = hashlib.md5(data_str.encode()).hexdigest()
        return f"{prefix}:{hash_str}"

    def _get_cached_response(self, key: str) -> Optional[Dict]:
        """Retrieves cached response if available from Redis or local SQLite."""
        if self.redis_client:
            try:
                cached = self.redis_client.get(key)
                if cached:
                    return json.loads(cached)
            except Exception as e:
                logger.error(f"Redis get error: {e}")

        # Local SQLite prompt cache fallback
        if getattr(self, "sqlite_cache_path", None):
            try:
                with sqlite3.connect(self.sqlite_cache_path) as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT value, expires_at FROM prompt_cache WHERE key = ?", (key,))
                    row = cur.fetchone()
                    if row:
                        val_str, expires_at = row
                        if expires_at > time.time():
                            return json.loads(val_str)
                        else:
                            cur.execute("DELETE FROM prompt_cache WHERE key = ?", (key,))
                            conn.commit()
            except Exception as e:
                logger.debug(f"SQLite cache get error: {e}")

        return None

    def _set_cached_response(self, key: str, data: Any, ttl: int = 3600):
        """Stores response in Redis and/or local SQLite cache."""
        payload_str = json.dumps(data)
        if self.redis_client:
            try:
                self.redis_client.setex(key, ttl, payload_str)
            except Exception as e:
                logger.error(f"Redis set error: {e}")

        if getattr(self, "sqlite_cache_path", None):
            try:
                expires_at = time.time() + ttl
                with sqlite3.connect(self.sqlite_cache_path) as conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO prompt_cache (key, value, expires_at) VALUES (?, ?, ?)",
                        (key, payload_str, expires_at)
                    )
                    conn.commit()
            except Exception as e:
                logger.debug(f"SQLite cache set error: {e}")

    def _construct_system_prompt(self, dietary_preferences: List[str] = None, allergies: List[str] = None) -> str:
        """
        Constructs a system prompt that incorporates dietary restrictions and allergies.
        """
        dietary_preferences = dietary_preferences or []
        allergies = allergies or []

        base_prompt = "You are a helpful meal planning assistant that outputs valid JSON."

        restrictions = []
        if dietary_preferences:
            restrictions.append(f"Dietary preferences: {', '.join(dietary_preferences)}")
        if allergies:
            restrictions.append(f"Allergies to avoid: {', '.join(allergies)}")

        if restrictions:
            restriction_text = " ".join(restrictions)
            return (
                f"{base_prompt} "
                f"CRITICAL: The user has the following dietary restrictions: {restriction_text}. "
                "You MUST ensure that all recommended recipes strictly follow these requirements. "
                "Even though recipes are pre-filtered, you must remain vigilant in your selection and reasoning."
            )
        return base_prompt

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

    async def regenerate_single_meal(
        self,
        user: Any,
        day: str,
        meal_type: str,
        dietary_preferences: List[str],
        existing_meals: List[Dict[str, Any]],
        session,
        model_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generates a new, single meal, avoiding existing meals.
        """
        # This is a simplified version. A full implementation would need
        # access to the full recipe DB and deals, similar to the main planner.

        recipe_service = RecipeService(session)
        deal_service = DealService(session)

        # Fetch necessary data
        all_recipes = await recipe_service.get_all_recipes_as_dicts()
        active_deals = await deal_service.get_active_deals_as_dicts()

        # Pre-filter recipes based on dietary preferences and allergies
        user_allergies = getattr(user, 'allergies', [])
        filtered_recipes = RecipeService.filter_recipes(all_recipes, dietary_preferences, user_allergies)

        if not filtered_recipes:
            # If no recipes match, we cannot generate a safe meal.
            # Returning None will trigger the fallback which should also be safe.
            logger.warning(f"No safe recipes found for user {user.id} during single meal regeneration.")
            return None

        prompt = self._construct_regenerate_meal_prompt(
            user, day, meal_type, dietary_preferences, existing_meals, filtered_recipes, active_deals
        )

        system_prompt = self._construct_system_prompt(dietary_preferences, user_allergies)

        try:
            response = self._call_llm(prompt, system_prompt=system_prompt, model_type=model_type)
            new_meal = self._parse_llm_response(response)
            return new_meal.get(meal_type.lower())
        except Exception as e:
            logger.error(f"LLM single meal generation failed: {e}. Falling back to mock.")
            return self._generate_mock_single_meal(meal_type, filtered_recipes)

    def _construct_regenerate_meal_prompt(
        self,
        user: Any,
        day: str,
        meal_type: str,
        dietary_preferences: List[str],
        existing_meals: List[Dict[str, Any]],
        recipes: List[Dict],
        deals: List[Dict],
    ) -> str:
        """
        Constructs the prompt for regenerating a single meal.
        """
        existing_meal_names = [
            meal.get("recipe_name") or meal.get("name") for meal in existing_meals if meal
        ]
        formatted_deals = self.format_deals_for_llm(deals)
        seasonal_context = self._get_seasonal_context()

        return f"""
        Generate a single replacement meal for a user's meal plan.

        {seasonal_context}

        USER CONTEXT:
        - Household Size: {user.household_size}
        - Dietary Preferences: {json.dumps(dietary_preferences)}

        REPLACEMENT DETAILS:
        - Day: {day}
        - Meal Type: {meal_type}

        RULES:
        1.  The new meal MUST be different from these existing meals: {json.dumps(existing_meal_names)}.
        2.  The new meal MUST be a '{meal_type}'.
        3.  Prioritize recipes that use ingredients from the AVAILABLE DEALS.
        4.  Respect all dietary preferences.

        AVAILABLE DEALS:
        {formatted_deals}

        AVAILABLE RECIPES:
        {json.dumps(self._format_recipes_for_prompt(recipes))}

        RETURN JSON STRUCTURE for the single meal:
        {{
            "{meal_type.lower()}": {{
                "recipe_id": "recipe_003",
                "recipe_name": "New Recipe Name",
                "reason": "Why this meal was chosen (e.g., uses deals, meets preferences).",
                "servings": {user.household_size},
                "scaled_for_household": true
            }}
        }}
        """

    def _generate_mock_single_meal(self, meal_type: str, recipes: List[Dict]) -> Optional[Dict]:
        """Generates a single mock meal for fallback."""
        import random

        candidates = [
            r
            for r in recipes
            if str(r.get("meal_type")).lower() == meal_type.lower()
            or r.get("meal_type") == "Any"
        ]
        if not candidates:
            candidates = recipes

        if not candidates:
            return None

        recipe = random.choice(candidates)
        return {
            "recipe_id": recipe.get("id"),
            "recipe_name": f"Mock {meal_type}: {recipe.get('name', 'Surprise Meal')}",
            "reason": "Mock fallback for single meal regeneration.",
            "servings": 1,
            "scaled_for_household": True,
        }

    def generate_meal_plan(self, user_prefs: Dict, available_deals: List[Dict], recipes_db: List[Dict], user_favorites: List[int] = None, model_type: Optional[str] = None) -> Dict:
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
            "favorites": sorted(user_favorites),
            "model_type": model_type
        }
        cache_key = self._get_cache_key("meal_plan", cache_key_data)
        cached = self._get_cached_response(cache_key)
        if cached:
            logger.info("Returning cached meal plan")
            return cached

        prompt = self._construct_meal_plan_prompt(user_prefs, available_deals, recipes_db, week_dates, user_favorites)

        system_prompt = self._construct_system_prompt(
            user_prefs.get('dietary_preferences'),
            user_prefs.get('allergies')
        )

        try:
            response = self._call_llm(prompt, system_prompt=system_prompt, model_type=model_type)
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
    def _make_api_request(self, model: str, prompt: str, system_prompt: str = None, client: Optional[OpenAI] = None) -> str:
        """Makes a single, retriable API call to the LLM."""
        if not system_prompt:
            system_prompt = "You are a helpful meal planning assistant that outputs valid JSON."

        target_client = client or self.client
        completion = target_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            timeout=120,
        )
        content = completion.choices[0].message.content
        if not content:
            raise ValueError(f"Empty response from LLM model {model}")
        return content

    def _call_llm(self, prompt: str, system_prompt: str = None, model_type: Optional[str] = None) -> str:
        """
        Calls the LLM API, handling local Ollama endpoint, OpenRouter primary/fallback models, and retries.
        """
        if settings.USE_MOCK_AI:
            logger.info("Mock AI enabled. Triggering fallback.")
            raise APIError("Mock AI enabled", request=None, body=None)

        # Determine target model
        target_model = self.MODEL_MAPPING.get(model_type, self.model)

        # In local SQLite mode or when OpenRouter API key is missing, attempt local Ollama first
        if (settings.USE_SQLITE_LOCAL or not settings.OPENROUTER_API_KEY) and self.ollama_client:
            try:
                ollama_model = "llama3.1" if "llama" in target_model.lower() else target_model
                logger.info(f"Calling local Ollama endpoint at {self.ollama_base_url} with model {ollama_model}")
                return self._make_api_request(ollama_model, prompt, system_prompt=system_prompt, client=self.ollama_client)
            except Exception as e:
                logger.warning(f"Local Ollama call failed: {e}. Falling back to OpenRouter or mock...")

        # If OpenRouter API key is available, call OpenRouter
        if settings.OPENROUTER_API_KEY:
            try:
                logger.info(f"Calling LLM model: {target_model} (specialization: {model_type})")
                return self._make_api_request(target_model, prompt, system_prompt=system_prompt, client=self.client)
            except Exception as e:
                logger.warning(f"LLM model '{target_model}' failed after retries: {e}")

            # Try fallback model
            try:
                logger.info(f"Calling fallback LLM model: {self.fallback_model}")
                return self._make_api_request(self.fallback_model, prompt, system_prompt=system_prompt, client=self.client)
            except Exception as e2:
                logger.error(f"Fallback LLM model '{self.fallback_model}' also failed after retries: {e2}")

        raise APIError("Both Ollama and OpenRouter LLM models failed or are unavailable.", request=None, body=None)

    def _construct_meal_plan_prompt(self, user_prefs: Dict, deals: List[Dict], recipes: List[Dict], week_dates: List[Dict], user_favorites: List[int]) -> str:
        formatted_deals = self.format_deals_for_llm(deals)
        household_size = user_prefs.get('household_size', 1)
        seasonal_context = self._get_seasonal_context()

        return f"""
        Create a 7-day meal plan (Breakfast, Lunch, Dinner) for a user with these preferences: {json.dumps(user_prefs)}.

        GENERATE PLAN FOR: {week_dates[0]['date']} to {week_dates[6]['date']}

        {seasonal_context}

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
           - HIGH PRIORITY: Prioritize recipes with a HIGH `deal_score` (more ingredients on sale). Use the provided `on_sale_ingredients` for context.
           - MEDIUM PRIORITY: Prioritize recipes with a high average rating (4 stars or higher).
        3. GENERAL RULES:
           - Never repeat the same meal or protein source on consecutive days.
           - Space repeated meals at least 3 days apart.
           - Ensure variety in cuisines.
           - Respect dietary restrictions and allergies. MANDATORY: ONLY use the provided recipes as they have been pre-filtered for safety.

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
                except Exception:
                    ingredients = []
            # Legacy format check
            elif isinstance(ingredients, list) and len(ingredients) > 0 and isinstance(ingredients[0], dict):
                 ingredients = [i.get('item', '') for i in ingredients]

            nutrition = r.get('nutrition', {})
            allergens = r.get('allergens', [])
            if isinstance(allergens, str):
                try:
                    allergens = json.loads(allergens)
                except Exception:
                    allergens = []

            dietary_tags = r.get('dietary_tags', [])
            if isinstance(dietary_tags, str):
                try:
                    dietary_tags = json.loads(dietary_tags)
                except Exception:
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
                'dietary_tags': dietary_tags,
                'deal_score': r.get('deal_score', 0),
                'on_sale_ingredients': r.get('on_sale_ingredients', [])
            })
        return formatted

    def _generate_mock_plan(self, user_prefs: Dict, recipes: List[Dict], week_dates: List[Dict]) -> Dict:
        """Fallback mock plan generation."""
        import random

        # Filter recipes by dietary preferences and allergies
        dietary_preferences = user_prefs.get('dietary_preferences', [])
        user_allergies = user_prefs.get('allergies', [])

        suitable_recipes = RecipeService.filter_recipes(recipes, dietary_preferences, user_allergies)

        if not suitable_recipes:
            logger.warning("No recipes match strict dietary preferences; falling back to all available recipes.")
            suitable_recipes = recipes

        days = []
        for i, date_info in enumerate(week_dates):
            day_meals = {}
            for m_type in ["Breakfast", "Lunch", "Dinner"]:
                # Filter by meal type if available in recipe
                candidates = [r for r in suitable_recipes if str(r.get("meal_type")).lower() == m_type.lower() or r.get("meal_type") == 'Any']
                if not candidates:
                    candidates = suitable_recipes

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
