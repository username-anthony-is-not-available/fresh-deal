import json
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime, date, timezone

def utc_now():
    return datetime.now(timezone.utc)

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    postal_code: str
    household_size: int
    dietary_preferences_json: Optional[str] = Field(default="[]")
    allergies_json: Optional[str] = Field(default="[]")
    preferred_loyalty_programs_json: Optional[str] = Field(default="[]")
    created_at: datetime = Field(default_factory=utc_now)

    ratings: List["RecipeRating"] = Relationship(back_populates="user")
    feedback: List["RecipeFeedback"] = Relationship(back_populates="user")
    favorites: List["UserFavorite"] = Relationship(back_populates="user")
    nutrition_goal: Optional["UserNutritionGoal"] = Relationship(back_populates="user")
    daily_nutritions: List["DailyNutrition"] = Relationship(back_populates="user")

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


from datetime import timedelta

class Store(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    chain: str  # Walmart, Provigo, IGA
    postal_code: str
    address: Optional[str] = None
    last_scraped_at: Optional[datetime] = Field(default=None)

    @property
    def is_stale(self) -> bool:
        if not self.last_scraped_at:
            return True
        return self.last_scraped_at < datetime.now(timezone.utc) - timedelta(days=7)

class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    category: str  # Produce, Meat, Dairy, etc.
    unit_type: str # kg, lb, each

    deals: List["Deal"] = Relationship(back_populates="product")

class Deal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id")
    store_id: int = Field(foreign_key="store.id")
    price: float
    original_price: Optional[float] = None
    discount_pct: Optional[float] = None
    valid_from: date
    valid_until: date

    loyalty_program: Optional[str] = None
    loyalty_points: Optional[int] = None

    product: Product = Relationship(back_populates="deals")
    store: Store = Relationship(link_model=None) # Simple relationship

class Recipe(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    cuisine: Optional[str] = None
    category: Optional[str] = None # e.g. "Main Dish"
    meal_type: Optional[str] = None # Breakfast, Lunch, Dinner (inferred or explicit)

    ingredients_json: str = Field(default="[]") # JSON list of strings (display)
    instructions_json: str = Field(default="[]") # JSON list of strings (display)
    allergens_json: str = Field(default="[]")
    dietary_tags_json: str = Field(default="[]")
    nutrition_json: str = Field(default="{}")

    prep_time_minutes: Optional[int] = None
    difficulty: Optional[str] = None
    image_url: Optional[str] = None
    source_url: Optional[str] = None

    # Matching helpers
    ingredients: List["RecipeIngredient"] = Relationship(back_populates="recipe")

    ratings: List["RecipeRating"] = Relationship(back_populates="recipe")
    feedback: List["RecipeFeedback"] = Relationship(back_populates="recipe")
    favorited_by: List["UserFavorite"] = Relationship(back_populates="recipe")

class RecipeIngredient(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="recipe.id")
    name: str = Field(index=True) # Normalized name for matching (e.g. "chicken")
    original_text: Optional[str] = None # "2 lbs chicken breast"

    recipe: Recipe = Relationship(back_populates="ingredients")

class MealPlan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    start_date: date
    end_date: date
    content_json: str # Stores the full JSON structure of meals
    created_at: datetime = Field(default_factory=utc_now)

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
