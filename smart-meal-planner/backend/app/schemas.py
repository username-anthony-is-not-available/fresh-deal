from pydantic import BaseModel
from typing import Optional

class UserUpdate(BaseModel):
    postal_code: Optional[str] = None
    household_size: Optional[int] = None
    dietary_preferences: Optional[str] = None

class UserRead(BaseModel):
    id: int
    postal_code: str
    household_size: int
    dietary_preferences: Optional[str] = None

    class Config:
        orm_mode = True


class RecipeFeedbackCreate(BaseModel):
    status: str
    notes: Optional[str] = None

class UserNutritionGoalCreate(BaseModel):
    goal_type: str = "maintenance"
    target_calories: Optional[float] = None
    target_protein: Optional[float] = None
    target_carbs: Optional[float] = None
    target_fats: Optional[float] = None

class UserNutritionGoalRead(UserNutritionGoalCreate):
    id: int
    user_id: int

    class Config:
        orm_mode = True

class DailyNutritionRead(BaseModel):
    id: int
    user_id: int
    date: str
    calories: float
    protein: float
    carbs: float
    fats: float
    micronutrients_json: str

    class Config:
        orm_mode = True
