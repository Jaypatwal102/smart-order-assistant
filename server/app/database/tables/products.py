import uuid
import enum
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Text, DateTime, Enum, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base, GUID

if TYPE_CHECKING:
    from app.database.tables.orders import Order


class ProductType(str, enum.Enum):
    COSMETIC = "COSMETIC"
    ELECTRONIC = "ELECTRONIC"
    FOOD = "FOOD"


class Product(Base):
    __tablename__ = "products"

    pid: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_type: Mapped[ProductType | None] = mapped_column(Enum(ProductType), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    orders: Mapped[list["Order"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
