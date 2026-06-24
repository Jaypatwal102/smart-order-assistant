from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Numeric, Text, Boolean, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, GUID

if TYPE_CHECKING:
    from app.models.orders import Order


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.00)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))

    orders: Mapped[list[Order]] = relationship(back_populates="product")
