from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
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
    from app.models.users import User


class Intent(Base):
    __tablename__ = "intents"

    intent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    intent_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    primary_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        server_default=text("'en'"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    training_phrases: Mapped[list[IntentTrainingPhrase]] = relationship(
        back_populates="intent",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    fallback_reviews: Mapped[list[FallbackReview]] = relationship(
        back_populates="assigned_intent",
        passive_deletes=True,
    )


class IntentTrainingPhrase(Base):
    __tablename__ = "intent_training_phrases"

    phrase_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    intent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intents.intent_id", ondelete="CASCADE"),
    )
    phrase_text: Mapped[str] = mapped_column(Text, nullable=False)
    language_code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        server_default=text("'en'"),
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    intent: Mapped[Intent | None] = relationship(back_populates="training_phrases")
    creator: Mapped[User | None] = relationship(back_populates="training_phrases")


class FallbackReview(Base):
    __tablename__ = "fallback_review_queue"
    __table_args__ = (
        CheckConstraint(
            "session_confidence IS NULL OR "
            "(session_confidence >= 0 AND session_confidence <= 1)",
            name="ck_fallback_review_queue_confidence",
        ),
        CheckConstraint(
            "reviewed_status IN ('pending', 'approved', 'ignored')",
            name="ck_fallback_review_queue_status",
        ),
    )

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    unrecognized_text: Mapped[str] = mapped_column(Text, nullable=False)
    session_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    detected_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        server_default=text("'en'"),
    )
    reviewed_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )
    assigned_to_intent: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intents.intent_id", ondelete="SET NULL"),
    )

    assigned_intent: Mapped[Intent | None] = relationship(
        back_populates="fallback_reviews"
    )
