import uuid
import enum
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Text, DateTime, Enum, ForeignKey, Boolean, func, text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base, GUID

if TYPE_CHECKING:
    from app.database.tables.users import User
    from app.database.tables.orders import Order
    from app.database.tables.conversations import Conversation


class ActionType(str, enum.Enum):
    SHIPPING_ADDRESS_UPDATE = "SHIPPING_ADDRESS_UPDATE"
    CANCEL_ORDER = "CANCEL_ORDER"
    REFUND_ORDER = "REFUND_ORDER"
    REPLACE_ORDER = "REPLACE_ORDER"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    audit_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    uid: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.uid", ondelete="CASCADE"),
        nullable=False,
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("orders.order_id", ondelete="SET NULL"),
        nullable=True,
    )
    cid: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("conversations.cid", ondelete="SET NULL"),
        nullable=True,
    )
    action_type: Mapped[ActionType | None] = mapped_column(Enum(ActionType), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_handoff: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="audit_logs")
    order: Mapped["Order"] = relationship(back_populates="audit_logs")
    conversation: Mapped["Conversation"] = relationship(back_populates="audit_logs")
