from pydantic import BaseModel, Field
from typing import List, Optional

class Ingredient(BaseModel):
    item: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    is_on_sale: bool = False
    deal_description: Optional[str] = None

class Nutrition(BaseModel):
    calories: Optional[float] = None
    protein: Optional[float] = None
    carbs: Optional[float] = None
    fat: Optional[float] = None
    fiber: Optional[float] = None

class GeneratedRecipe(BaseModel):
    name: str
    description: str
    ingredients: List[Ingredient]
    instructions: List[str]
    prep_time_minutes: int
    servings: int
    nutrition: Nutrition
    cuisine: Optional[str] = None
    dietary_tags: List[str] = []

class MealSuggestion(BaseModel):
    recipe: GeneratedRecipe
    deal_reasoning: str = Field(..., description="Explanation of how this recipe utilizes active grocery deals")
    estimated_savings: float = 0.0

class InnovativeMealPlan(BaseModel):
    suggestions: List[MealSuggestion]
    total_estimated_savings: float = 0.0
    shopping_list_notes: str
