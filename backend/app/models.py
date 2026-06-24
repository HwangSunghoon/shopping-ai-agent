from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SearchSession(Base):
    __tablename__ = "search_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    conditions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    search_queries_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    intent_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    search_terms_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    raw_products_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    candidate_products_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    recommended_products_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    assistant_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    assistant_mode: Mapped[str] = mapped_column(Text, nullable=False, default="llm")
    fallback_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    llm_failed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fallback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    clarification_questions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chat_turns: Mapped[list["ChatTurn"]] = relationship(
        back_populates="search_session",
        cascade="all, delete-orphan",
        order_by="ChatTurn.created_at.asc()",
    )

    def __init__(self, **kwargs):
        fallback_used = kwargs.pop("fallback_used", None)
        if fallback_used is not None and "fallback_active" not in kwargs:
            kwargs["fallback_active"] = fallback_used
        super().__init__(**kwargs)


class ChatTurn(Base):
    __tablename__ = "chat_turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    search_session_id: Mapped[int] = mapped_column(ForeignKey("search_sessions.id"), nullable=False)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    assistant_message: Mapped[str] = mapped_column(Text, nullable=False)
    fallback_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fallback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    search_session: Mapped[SearchSession] = relationship(back_populates="chat_turns")

    def __init__(self, **kwargs):
        fallback_used = kwargs.pop("fallback_used", None)
        if fallback_used is not None and "fallback_active" not in kwargs:
            kwargs["fallback_active"] = fallback_used
        super().__init__(**kwargs)


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    preference_type: Mapped[str] = mapped_column(String(80), nullable=False)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="manual")
    positive_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    negative_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserEvent(Base):
    __tablename__ = "user_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserMemory(Base):
    __tablename__ = "user_memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    memory_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    strength: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
