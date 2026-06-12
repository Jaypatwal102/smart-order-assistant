from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.users import User, UserSession


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'completed', 'handed_over')",
            name="ck_conversations_status",
        ),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_sessions.session_id", ondelete="SET NULL"),
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",
        server_default=text("'active'"),
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)

    session: Mapped[UserSession | None] = relationship(back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    fallback_handoffs: Mapped[list[FallbackHandoff]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "sender_type IN ('user', 'bot', 'human_agent')",
            name="ck_messages_sender_type",
        ),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
    )
    sender_type: Mapped[str] = mapped_column(String(50), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    audio_url: Mapped[str | None] = mapped_column(String(512))
    input_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        server_default=text("'en'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    conversation: Mapped[Conversation | None] = relationship(back_populates="messages")
    routing_logs: Mapped[list[BotRoutingLog]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    triggered_handoffs: Mapped[list[FallbackHandoff]] = relationship(
        back_populates="trigger_message",
    )


class BotRoutingLog(Base):
    __tablename__ = "bot_routing_logs"
    __table_args__ = (
        CheckConstraint(
            "confidence_score IS NULL OR "
            "(confidence_score >= 0 AND confidence_score <= 1)",
            name="ck_bot_routing_logs_confidence",
        ),
        CheckConstraint(
            "routed_flow IS NULL OR "
            "routed_flow IN ('Flow_A_Deterministic', 'Flow_B_Generative')",
            name="ck_bot_routing_logs_routed_flow",
        ),
        CheckConstraint(
            "execution_time_ms IS NULL OR execution_time_ms >= 0",
            name="ck_bot_routing_logs_execution_time",
        ),
    )

    routing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.message_id", ondelete="CASCADE"),
    )
    detected_intent: Mapped[str | None] = mapped_column(String(100))
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    routed_flow: Mapped[str | None] = mapped_column(String(100))
    execution_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        server_default=text("'en'"),
    )
    execution_time_ms: Mapped[int | None] = mapped_column(Integer)

    message: Mapped[Message | None] = relationship(back_populates="routing_logs")


class FallbackHandoff(Base):
    __tablename__ = "fallback_handoffs"

    fallback_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
    )
    trigger_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.message_id"),
    )
    fallback_reason: Mapped[str | None] = mapped_column(String(255))
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)

    conversation: Mapped[Conversation | None] = relationship(
        back_populates="fallback_handoffs"
    )
    trigger_message: Mapped[Message | None] = relationship(
        back_populates="triggered_handoffs"
    )
    assigned_agent: Mapped[User | None] = relationship(
        back_populates="assigned_handoffs"
    )
