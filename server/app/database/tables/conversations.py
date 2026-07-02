import uuid
import enum
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base, GUID

if TYPE_CHECKING:
    from app.database.tables.users import User
    from app.database.tables.messages import Message
    from app.database.tables.audit_logs import AuditLog


class ConversationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class Conversation(Base):
    __tablename__ = "conversations"

    cid: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    uid: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.uid", ondelete="CASCADE"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    status: Mapped[ConversationStatus | None] = mapped_column(Enum(ConversationStatus), nullable=True)

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
