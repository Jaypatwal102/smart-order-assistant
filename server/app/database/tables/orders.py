import uuid
import enum
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Text, DateTime, Enum, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base, GUID

if TYPE_CHECKING:
    from app.database.tables.users import User
    from app.database.tables.products import Product
    from app.database.tables.audit_logs import AuditLog


class OrderStatus(str, enum.Enum):
    ORDERED = "ORDERED"
    DISPATCHED = "DISPATCHED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REPLACED = "REPLACED"
    REFUNDED = "REFUNDED"


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    uid: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.uid", ondelete="CASCADE"),
        nullable=False,
    )
    pid: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("products.pid", ondelete="SET NULL"),
        nullable=True,
    )
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    order_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    order_status: Mapped[OrderStatus | None] = mapped_column(Enum(OrderStatus), nullable=True)

    user: Mapped["User"] = relationship(back_populates="orders")
    product: Mapped["Product"] = relationship(back_populates="orders")
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
