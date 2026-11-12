import json
from typing import Optional, List
from sqlalchemy import Index
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime, date, timezone, timedelta
from app.core.crypto import EncryptedString, EncryptedInt


def utc_now():
    # Columns are TIMESTAMP WITHOUT TIME ZONE; asyncpg rejects tz-aware values, so store naive UTC.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    email_digest_enabled: bool = Field(default=False)
    postal_code: str = Field(sa_type=EncryptedString)
    household_size: int = Field(sa_type=EncryptedInt)
    dietary_preferences_json: Optional[str] = Field(default="[]", sa_type=EncryptedString)
    allergies_json: Optional[str] = Field(default="[]", sa_type=EncryptedString)
    preferred_loyalty_programs_json: Optional[str] = Field(default="[]")
    created_at: datetime = Field(default_factory=utc_now)

    ratings: List["RecipeRating"] = Relationship(back_populates="user")
    feedback: List["RecipeFeedback"] = Relationship(back_populates="user")
    feedbacks: List["Feedback"] = Relationship(back_populates="user")
    favorites: List["UserFavorite"] = Relationship(back_populates="user")
    nutrition_goal: Optional["UserNutritionGoal"] = Relationship(back_populates="user")
    daily_nutritions: List["DailyNutrition"] = Relationship(back_populates="user")
    pantry_items: List["PantryItem"] = Relationship(back_populates="user")

    @property
    def allergies(self) -> List[str]:
        if self.allergies_json:
            return json.loads(self.allergies_json)
        return []

    @allergies.setter
    def allergies(self, value: List[str]):
        self.allergies_json = json.dumps(value)

    @property
    def dietary_preferences(self) -> List[str]:
        if self.dietary_preferences_json:
            return json.loads(self.dietary_preferences_json)
        return []

    @dietary_preferences.setter
    def dietary_preferences(self, value: List[str]):
        self.dietary_preferences_json = json.dumps(value)


class Store(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    chain: str = Field(index=True)  # Walmart, Provigo, IGA
    postal_code: str = Field(index=True)
    address: Optional[str] = None
    last_scraped_at: Optional[datetime] = Field(default=None)

    @property
    def is_stale(self) -> bool:
        if not self.last_scraped_at:
            return True
        last_scraped = self.last_scraped_at
        if last_scraped.tzinfo is not None:
            last_scraped = last_scraped.replace(tzinfo=None)
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
        return last_scraped < cutoff


class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    category: str = Field(index=True)  # Produce, Meat, Dairy, etc.
    unit_type: str  # kg, lb, each

    deals: List["Deal"] = Relationship(back_populates="product")


class Deal(SQLModel, table=True):
    __table_args__ = (
        Index("ix_deal_valid_window_discount", "valid_from", "valid_until", "discount_pct"),
        Index("ix_deal_store_product_valid", "store_id", "product_id", "valid_until"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    store_id: int = Field(foreign_key="store.id", index=True)
    price: float
    original_price: Optional[float] = None
    discount_pct: Optional[float] = Field(default=None, index=True)
    valid_from: date = Field(index=True)
    valid_until: date = Field(index=True)

    loyalty_program: Optional[str] = None
    loyalty_points: Optional[int] = None
    quality_score: Optional[float] = Field(default=None, index=True)
    quality_level: Optional[str] = Field(default=None)
    image_url: Optional[str] = Field(default=None)
    sale_info: Optional[str] = Field(default=None)

    product: Product = Relationship(back_populates="deals")
    store: Store = Relationship(link_model=None)  # Simple relationship


class Recipe(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    cuisine: Optional[str] = None
    category: Optional[str] = None  # e.g. "Main Dish"
    meal_type: Optional[str] = None  # Breakfast, Lunch, Dinner (inferred or explicit)

    ingredients_json: str = Field(default="[]")  # JSON list of strings (display)
    instructions_json: str = Field(default="[]")  # JSON list of strings (display)
    allergens_json: str = Field(default="[]")
    dietary_tags_json: str = Field(default="[]")
    nutrition_json: str = Field(default="{}")

    prep_time_minutes: Optional[int] = None
    difficulty: Optional[str] = None
    servings: int = Field(default=4)
    image_url: Optional[str] = None
    source_url: Optional[str] = None

    # Matching helpers
    ingredients: List["RecipeIngredient"] = Relationship(back_populates="recipe")

    ratings: List["RecipeRating"] = Relationship(back_populates="recipe")
    feedback: List["RecipeFeedback"] = Relationship(back_populates="recipe")
    feedbacks: List["Feedback"] = Relationship(back_populates="recipe")
    favorited_by: List["UserFavorite"] = Relationship(back_populates="recipe")


class RecipeIngredient(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="recipe.id")
    name: str = Field(index=True)  # Normalized name for matching (e.g. "chicken")
    original_text: Optional[str] = None  # "2 lbs chicken breast"

    recipe: Recipe = Relationship(back_populates="ingredients")


class MealPlan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    start_date: date
    end_date: date
    content_json: str  # Stores the full JSON structure of meals
    created_at: datetime = Field(default_factory=utc_now)

    feedbacks: List["Feedback"] = Relationship(back_populates="meal_plan")


class RecipeRating(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    recipe_id: int = Field(foreign_key="recipe.id")
    rating: int = Field(ge=1, le=5)
    created_at: datetime = Field(default_factory=utc_now)

    user: "User" = Relationship(back_populates="ratings")
    recipe: "Recipe" = Relationship(back_populates="ratings")


class RecipeFeedback(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    recipe_id: int = Field(foreign_key="recipe.id")
    status: str  # "made_it", "skipped"
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)

    user: "User" = Relationship(back_populates="feedback")
    recipe: "Recipe" = Relationship(back_populates="feedback")


class UserFavorite(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    recipe_id: int = Field(foreign_key="recipe.id")
    created_at: datetime = Field(default_factory=utc_now)

    user: "User" = Relationship(back_populates="favorites")
    recipe: "Recipe" = Relationship(back_populates="favorited_by")


class UserNutritionGoal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True)
    goal_type: str = Field(default="maintenance")  # "weight_loss", "muscle_gain"
    target_calories: Optional[float] = None
    target_protein: Optional[float] = None
    target_carbs: Optional[float] = None
    target_fats: Optional[float] = None
    target_fiber: Optional[float] = None
    updated_at: datetime = Field(default_factory=utc_now)

    user: "User" = Relationship(back_populates="nutrition_goal")


class DailyNutrition(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    date: date
    calories: float
    protein: float
    carbs: float
    fats: float
    fiber: Optional[float] = None
    micronutrients_json: str = Field(default="{}")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    user: "User" = Relationship(back_populates="daily_nutritions")


class PantryItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(index=True)
    quantity: float = Field(default=0)
    unit: str = Field(default="each")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    user: "User" = Relationship(back_populates="pantry_items")


class Feedback(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    recipe_id: Optional[int] = Field(default=None, foreign_key="recipe.id")
    meal_plan_id: Optional[int] = Field(default=None, foreign_key="mealplan.id")
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)

    user: "User" = Relationship(back_populates="feedbacks")
    recipe: Optional["Recipe"] = Relationship(back_populates="feedbacks")
    meal_plan: Optional["MealPlan"] = Relationship(back_populates="feedbacks")


class ScraperLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    store_name: str = Field(index=True)
    status: str  # "success", "failure"
    scraper_type: Optional[str] = Field(default="direct")  # "direct", "flipp", "fallback"
    proxy_used: Optional[str] = None
    items_scraped: int = Field(default=0)
    duration_seconds: float = Field(default=0.0)
    error_message: Optional[str] = None
    postal_code: Optional[str] = Field(default=None)
    screenshot_path: Optional[str] = None
    html_path: Optional[str] = None
    timestamp: datetime = Field(default_factory=utc_now)


class PriceRecord(SQLModel, table=True):
    __table_args__ = (
        Index("ix_pricerecord_product_store_ts", "product_id", "store_id", "timestamp"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    store_id: int = Field(foreign_key="store.id", index=True)
    price: float
    timestamp: datetime = Field(default_factory=utc_now)
