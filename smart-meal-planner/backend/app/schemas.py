from pydantic import BaseModel
from typing import Optional

class UserUpdate(BaseModel):
    postal_code: Optional[str] = None
    household_size: Optional[int] = None
    dietary_preferences: Optional[str] = None
    allergies: Optional[list[str]] = None

    class Config:
        schema_extra = {
            "example": {
                "household_size": 2,
                "dietary_preferences": "vegetarian"
            }
        }

class UserRead(BaseModel):
    id: int
    postal_code: str
    household_size: int
    dietary_preferences: Optional[str] = None
    allergies: Optional[list[str]] = None

    class Config:
        orm_mode = True

class NutritionSummaryRead(BaseModel):
    totals: dict
    daily_averages: dict

class RecipeRead(BaseModel):
    id: int
    name: str
    cuisine: Optional[str] = None
    meal_type: Optional[str] = None
    prep_time_minutes: Optional[int] = None
    difficulty: Optional[str] = None
    allergens: list[str] = []

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "id": 1,
                "postal_code": "H4T1V6",
                "household_size": 4,
                "dietary_preferences": "none"
            }
        }


class RecipeFeedbackCreate(BaseModel):
    status: str
    notes: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "status": "made_it",
                "notes": "The cooking time was a bit too long."
            }
        }

class UserNutritionGoalCreate(BaseModel):
    goal_type: str = "maintenance"
    target_calories: Optional[float] = None
    target_protein: Optional[float] = None
    target_carbs: Optional[float] = None
    target_fats: Optional[float] = None
    target_fiber: Optional[float] = None

    class Config:
        schema_extra = {
            "example": {
                "goal_type": "weight_loss",
                "target_calories": 2000,
                "target_protein": 150
            }
        }

class UserNutritionGoalRead(UserNutritionGoalCreate):
    id: int
    user_id: int

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "id": 1,
                "user_id": 1,
                "goal_type": "weight_loss",
                "target_calories": 2000,
                "target_protein": 150,
                "target_carbs": 200,
                "target_fats": 60
            }
        }

class DailyNutritionRead(BaseModel):
    id: int
    user_id: int
    date: str
    calories: float
    protein: float
    carbs: float
    fats: float
    fiber: Optional[float] = None
    micronutrients_json: str

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "id": 1,
                "user_id": 1,
                "date": "2024-07-29",
                "calories": 2100.5,
                "protein": 155.2,
                "carbs": 205.0,
                "fats": 65.8,
                "micronutrients_json": "{\"vitamin_c\": 80, \"iron\": 15}"
            }
        }
