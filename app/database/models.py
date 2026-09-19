from datetime import datetime

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Float,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    timezone: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    language_preference: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
    )

    last_seen: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
    )

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user",
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="user",
    )

    memories: Mapped[list["Memory"]] = relationship(
        back_populates="user",
    )


class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id"),
        nullable=False,
    )

    last_interaction_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    message_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    user: Mapped["User"] = relationship(
        back_populates="conversations",
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
    )

    session_interactions: Mapped[list["SessionInteraction"]] = relationship(
        back_populates="conversation",
    )


class Message(Base):
    __tablename__ = "messages"

    message_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.conversation_id"),
        nullable=False,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id"),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    timestamp: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
    )

    gemini_interaction_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    conversation: Mapped["Conversation"] = relationship(
        back_populates="messages",
    )

    user: Mapped["User"] = relationship(
        back_populates="messages",
    )


class Memory(Base):
    __tablename__ = "memory"

    memory_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id"),
        nullable=False,
    )

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    importance: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        default=0.8,
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
    )

    user: Mapped["User"] = relationship(
        back_populates="memories",
    )


class SessionInteraction(Base):
    __tablename__ = "session_interactions"

    session_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.conversation_id"),
        nullable=False,
    )

    last_interaction_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    last_message_timestamp: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    session_started: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
    )

    conversation: Mapped["Conversation"] = relationship(
        back_populates="session_interactions",
    )


class Reminder(Base):
    __tablename__ = "reminders"

    reminder_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id"),
        nullable=False,
    )

    channel_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    remind_at: Mapped[datetime] = mapped_column(
        nullable=False,
    )

    completed: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
    )

    user: Mapped["User"] = relationship()


# Performance indexes

Index(
    "ix_messages_user_timestamp",
    Message.user_id,
    Message.timestamp,
)

Index(
    "ix_messages_conversation",
    Message.conversation_id,
)

Index(
    "ix_memory_user_category",
    Memory.user_id,
    Memory.category,
)

Index(
    "ix_memory_user_importance",
    Memory.user_id,
    Memory.importance,
)

Index(
    "ix_conversations_user_ended",
    Conversation.user_id,
    Conversation.ended_at,
)

Index(
    "ix_session_interactions_last_message",
    SessionInteraction.last_message_timestamp,
)