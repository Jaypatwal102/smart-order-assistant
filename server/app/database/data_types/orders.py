import uuid
from datetime import datetime
from pydantic import BaseModel
from app.database.tables.orders import OrderStatus

class OrderBase(BaseModel):
    uid: uuid.UUID
    pid: uuid.UUID | None = None
    delivery_address: str | None = None
    delivery_date: datetime | None = None
    order_price: float
    order_status: OrderStatus | None = None

class OrderCreate(OrderBase):
    pass

class OrderResponse(OrderBase):
    order_id: uuid.UUID

    class Config:
        from_attributes = True
