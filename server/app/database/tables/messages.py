import uuid
import enum
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Text, DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base, GUID

if TYPE_CHECKING:
    from app.database.tables.conversations import Conversation


class SenderType(str, enum.Enum):
    USER = "USER"
    BOT = "BOT"
    HUMAN_AGENT = "HUMAN_AGENT"


class Message(Base):
    __tablename__ = "messages"

    mid: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    cid: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("conversations.cid", ondelete="CASCADE"),
        nullable=False,
    )
    sender_type: Mapped[SenderType | None] = mapped_column(Enum(SenderType), nullable=True)
    message_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
