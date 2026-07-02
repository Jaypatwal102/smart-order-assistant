import uuid
from datetime import datetime
from pydantic import BaseModel
from app.database.tables.products import ProductType

class ProductBase(BaseModel):
    product_name: str
    price: float
    description: str | None = None
    product_type: ProductType | None = None

class ProductCreate(ProductBase):
    pass

class ProductResponse(ProductBase):
    pid: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True
