from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime, date

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    postal_code: str
    household_size: int
    dietary_preferences: Optional[str] = None  # JSON string or comma-separated
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Store(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    chain: str  # Walmart, Provigo, IGA
    postal_code: str
    address: Optional[str] = None

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

    product: Product = Relationship(back_populates="deals")
    store: Store = Relationship(link_model=None) # Simple relationship

class MealPlan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    start_date: date
    end_date: date
    content_json: str # Stores the full JSON structure of meals
    created_at: datetime = Field(default_factory=datetime.utcnow)
