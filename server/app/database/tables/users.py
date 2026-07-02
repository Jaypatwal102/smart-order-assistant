import uuid
import enum
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Text, DateTime, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base, GUID

if TYPE_CHECKING:
    from app.database.tables.orders import Order
    from app.database.tables.conversations import Conversation
    from app.database.tables.audit_logs import AuditLog


class UserRole(str, enum.Enum):
    USER = "USER"
    HUMAN_AGENT = "HUMAN_AGENT"


class User(Base):
    __tablename__ = "users"

    uid: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[UserRole | None] = mapped_column(Enum(UserRole), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    orders: Mapped[list["Order"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
