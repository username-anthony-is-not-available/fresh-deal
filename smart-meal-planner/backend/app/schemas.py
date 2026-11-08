import datetime
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List, Dict, Any


class UserBase(BaseModel):
    email: EmailStr
    postal_code: str
    household_size: int
    dietary_preferences: Optional[str] = None
    allergies: Optional[str] = None
    weekly_budget: Optional[float] = None


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    email: Optional[EmailStr] = None
    postal_code: Optional[str] = None
    household_size: Optional[int] = None
    dietary_preferences: Optional[str] = None
    allergies: Optional[str] = None
    weekly_budget: Optional[float] = None
    email_digest_enabled: Optional[bool] = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    postal_code: str
    household_size: int
    dietary_preferences: Optional[str] = None
    allergies: Optional[str] = None
    weekly_budget: Optional[float] = None
    email_digest_enabled: bool = False


class FeedbackCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": 1,
                "recipe_id": 1,
                "meal_plan_id": None,
                "rating": 5,
                "comment": "This recipe was delicious and very affordable!",
            }
        }
    )
    user_id: int
    recipe_id: Optional[int] = None
    meal_plan_id: Optional[int] = None
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class FeedbackRead(FeedbackCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime.datetime


class NutritionSummaryRead(BaseModel):
    totals: dict
    daily_averages: dict


class RecipeRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "Spaghetti Bolognese",
                "cuisine": "Italian",
                "meal_type": "Dinner",
                "prep_time_minutes": 60,
                "difficulty": "Easy",
                "ingredients": ["ground beef", "spaghetti", "tomato sauce"],
                "substitutions": {"ground beef": ["ground turkey", "lentils"]},
            }
        }
    )
    id: int
    name: str
    cuisine: Optional[str] = None
    meal_type: Optional[str] = None
    prep_time_minutes: Optional[int] = None
    difficulty: Optional[str] = None
    servings: int = 4
    ingredients: List[Any] = []
    substitutions: Dict[str, List[str]] = {}
    allergens: list[str] = []
    average_rating: float = 0


class RecipeIngestion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: Optional[str] = None
    name: str
    cuisine: Optional[str] = None
    meal_type: Optional[str] = "Dinner"
    prep_time_minutes: Optional[int] = 30
    difficulty: Optional[str] = "easy"
    servings: int = 4
    ingredients: List[Any]
    nutrition: Optional[Dict[str, Any]] = None
    instructions: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    dietary_tags: Optional[List[str]] = None
    allergens: Optional[List[str]] = None


class RecipeFeedbackCreate(BaseModel):
    status: str


class RecipeRatingCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)


class RecipeRatingRead(RecipeRatingCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    recipe_id: int


class UserNutritionGoalCreate(BaseModel):
    daily_calories: Optional[int] = Field(None, ge=500, le=10000)
    daily_protein: Optional[float] = Field(None, ge=0, le=1000)
    daily_carbs: Optional[float] = Field(None, ge=0, le=1000)
    daily_fat: Optional[float] = Field(None, ge=0, le=1000)
    daily_fiber: Optional[float] = Field(None, ge=0, le=200)


class UserNutritionGoalRead(UserNutritionGoalCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    updated_at: datetime.datetime


class DailyNutritionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    date: datetime.date
    calories: Optional[float] = None
    protein: Optional[float] = None
    carbs: Optional[float] = None
    fat: Optional[float] = None
    fiber: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime.datetime


class DealRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    store_id: int
    price: float
    original_price: Optional[float] = None
    discount_pct: Optional[float] = None
    valid_from: Optional[datetime.date] = None
    valid_until: Optional[datetime.date] = None
    loyalty_program: Optional[str] = None
    loyalty_points: Optional[int] = None
    sale_info: Optional[str] = None
    image_url: Optional[str] = None
    quality_score: Optional[float] = None
    quality_level: Optional[str] = None


class PantryItemCreate(BaseModel):
    name: str
    quantity: float = 1.0
    unit: str = "each"


class PantryAddRequest(BaseModel):
    items: List[PantryItemCreate]


class PantryItemRead(BaseModel):
    id: Optional[int] = None
    user_id: int
    name: str
    quantity: float
    unit: str
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)

