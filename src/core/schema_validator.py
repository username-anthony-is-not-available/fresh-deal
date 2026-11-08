from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date

class Deal(BaseModel):
    """
    Standard schema for a grocery deal across different stores.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Apples",
                "price": 2.99,
                "original_price": 3.99,
                "unit": "bag",
                "store": "Provigo",
                "category": "Produce",
                "image_url": "https://example.com/apples.png",
                "sale_info": "Save $1.00"
            }
        }
    )

    name: str = Field(..., description="The name of the product")
    price: float = Field(..., description="The current sale price")
    original_price: Optional[float] = Field(None, description="The regular price if available")
    unit: str = Field("each", description="The pricing unit (e.g., kg, lb, each)")
    store: str = Field(..., description="The store name (e.g., Provigo, Metro)")
    category: str = Field("Grocery", description="The product category")
    image_url: Optional[str] = Field(None, description="URL to the product image")
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    loyalty_program: Optional[str] = None
    loyalty_points: Optional[int] = None
    sale_info: Optional[str] = Field(None, description="Raw sale text (e.g., '2 for $5.00')")
