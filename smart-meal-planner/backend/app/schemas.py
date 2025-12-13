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
