from datetime import datetime
import re

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.config import DB_PATH
from app.database.models import (
    User,
    Conversation,
    Message,
    Memory,
    SessionInteraction,
    Reminder,
)


class MemoryManager:
    SINGLETON_KEYS = {
        "name", "communication_language", "addressing_style",
        "favorite_game", "favorite_sport", "favorite_color", "greeting_style",
    }

    ALWAYS_RELEVANT_KEYS = {
        "communication_language", "addressing_style", "greeting_style",
    }

    CONCEPT_TERMS = {
        "favorite_game": {"favorite", "fav", "game", "sport", "khel"},
        "favorite_sport": {"favorite", "fav", "game", "sport", "khel"},
        "addressing_style": {"aap", "address", "respect", "baat", "bol", "tu", "teri"},
        "communication_language": {"language", "hinglish", "hindi", "english", "baat", "reply"},
        "name": {"name", "naam", "who", "kaun"},
    }

    def __init__(self) -> None:
        database_url = f"sqlite:///{DB_PATH}"

        self.engine = create_engine(
            database_url,
            echo=False,
        )

        self.SessionLocal = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

    def get_or_create_user(
        self,
        user_id: int,
        name: str | None = None,
    ) -> User:
        with self.SessionLocal() as session:
            user = session.get(User, user_id)

            if user is None:
                user = User(
                    user_id=user_id,
                    name=name,
                    created_at=datetime.utcnow(),
                    last_seen=datetime.utcnow(),
                )

                session.add(user)

            else:
                user.last_seen = datetime.utcnow()

                if name and not user.name:
                    user.name = name

            session.commit()
            session.refresh(user)

            return user

    def create_conversation(
        self,
        user_id: int,
    ) -> Conversation:
        with self.SessionLocal() as session:
            conversation = Conversation(
                user_id=user_id,
                started_at=datetime.utcnow(),
                message_count=0,
            )

            session.add(conversation)
            session.commit()
            session.refresh(conversation)

            return conversation

    def save_message(
        self,
        conversation_id: int,
        user_id: int,
        role: str,
        content: str,
        gemini_interaction_id: str | None = None,
    ) -> Message:
        with self.SessionLocal() as session:
            message = Message(
                conversation_id=conversation_id,
                user_id=user_id,
                role=role,
                content=content,
                timestamp=datetime.utcnow(),
                gemini_interaction_id=gemini_interaction_id,
            )

            session.add(message)

            conversation = session.get(
                Conversation,
                conversation_id,
            )

            if conversation:
                conversation.message_count += 1

                if gemini_interaction_id:
                    conversation.last_interaction_id = (
                        gemini_interaction_id
                    )

            session.commit()
            session.refresh(message)

            return message

    def get_recent_messages(
        self,
        conversation_id: int,
        limit: int = 10,
    ) -> list[Message]:
        with self.SessionLocal() as session:
            messages = session.scalars(
                select(Message)
                .where(
                    Message.conversation_id == conversation_id
                )
                .order_by(Message.timestamp.desc())
                .limit(limit)
            ).all()

            return list(reversed(messages))

    def save_memory(
        self,
        user_id: int,
        category: str,
        key: str,
        value: str,
        importance: int = 5,
        confidence: float = 0.8,
        source: str = "conversation",
    ) -> Memory:
        category = category.strip()
        key = key.strip().casefold()
        value = re.sub(r"\s+", " ", value.strip())

        with self.SessionLocal() as session:
            query = select(Memory).where(
                Memory.user_id == user_id,
                Memory.key == key,
            )

            # Latest-value preferences intentionally share one record; a
            # multi-value memory is unique by its key/value pair instead.
            if key not in self.SINGLETON_KEYS:
                query = query.where(
                    func.lower(Memory.value) == value.casefold()
                )

            memory = session.scalars(query).first()

            if memory:
                memory.category = category
                memory.value = value
                memory.importance = importance
                memory.confidence = confidence
                memory.source = source
                memory.updated_at = datetime.utcnow()

            else:
                memory = Memory(
                    user_id=user_id,
                    category=category,
                    key=key,
                    value=value,
                    importance=importance,
                    confidence=confidence,
                    source=source,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )

                session.add(memory)

            session.commit()
            session.refresh(memory)

            print(f"[MEMORY] Saved: user={user_id} key={key}")

            return memory

    def get_memories(
        self,
        user_id: int,
        min_importance: int = 1,
    ) -> list[Memory]:
        with self.SessionLocal() as session:
            memories = session.scalars(
                select(Memory)
                .where(
                    Memory.user_id == user_id,
                    Memory.importance >= min_importance,
                )
                .order_by(Memory.importance.desc())
            ).all()

            return list(memories)

    @staticmethod
    def _terms(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", text.casefold()))

    def get_relevant_memories(
        self,
        user_id: int,
        query: str,
        limit: int = 8,
    ) -> list[Memory]:
        """Return only turn-relevant memories plus high-priority instructions."""
        query_terms = self._terms(query)
        candidates = self.get_memories(
            user_id=user_id,
            min_importance=1,
        )
        ranked: list[tuple[float, Memory]] = []

        for memory in candidates:
            key_terms = self._terms(memory.key.replace("_", " "))
            value_terms = self._terms(memory.value)
            concept_terms = self.CONCEPT_TERMS.get(memory.key, set())
            overlap = len(query_terms & (key_terms | value_terms))
            concept_match = bool(query_terms & concept_terms)
            always_relevant = memory.key in self.ALWAYS_RELEVANT_KEYS

            if not (overlap or concept_match or always_relevant):
                continue

            score = overlap * 10 + (8 if concept_match else 0)
            score += memory.importance / 10
            if always_relevant:
                score += 6
            ranked.append((score, memory))

        ranked.sort(
            key=lambda item: (
                item[0],
                item[1].importance,
                item[1].updated_at,
            ),
            reverse=True,
        )

        return [memory for _, memory in ranked[:max(1, limit)]]

    # ------------------------------------------------------------------
    # Phase 7 - Memory UI / CRUD methods
    # ------------------------------------------------------------------

    def get_all_memory(
        self,
        user_id: int,
        category: str | None = None,
    ) -> list[Memory]:
        with self.SessionLocal() as session:
            query = (
                select(Memory)
                .where(Memory.user_id == user_id)
                .order_by(
                    Memory.importance.desc(),
                    Memory.updated_at.desc(),
                )
            )

            if category:
                query = query.where(
                    Memory.category == category
                )

            memories = session.scalars(query).all()

            return list(memories)

    def get_memory_by_id(
        self,
        user_id: int,
        memory_id: int,
    ) -> Memory | None:
        with self.SessionLocal() as session:
            return session.scalar(
                select(Memory).where(
                    Memory.memory_id == memory_id,
                    Memory.user_id == user_id,
                )
            )

    def get_memory_categories(
        self,
        user_id: int,
    ) -> list[dict]:
        with self.SessionLocal() as session:
            rows = session.execute(
                select(
                    Memory.category,
                    func.count(Memory.memory_id),
                )
                .where(Memory.user_id == user_id)
                .group_by(Memory.category)
                .order_by(Memory.category.asc())
            ).all()

            return [
                {
                    "category": category,
                    "count": count,
                }
                for category, count in rows
            ]

    def create_memory(
        self,
        user_id: int,
        key: str,
        value: str,
        category: str,
        importance: int = 5,
        confidence: float = 1.0,
        source: str = "manual",
    ) -> Memory:
        return self.save_memory(
            user_id=user_id,
            category=category,
            key=key,
            value=value,
            importance=importance,
            confidence=confidence,
            source=source,
        )

    def update_memory(
        self,
        user_id: int,
        memory_id: int,
        value: str | None = None,
        importance: int | None = None,
    ) -> Memory | None:
        with self.SessionLocal() as session:
            memory = session.scalar(
                select(Memory).where(
                    Memory.memory_id == memory_id,
                    Memory.user_id == user_id,
                )
            )

            if memory is None:
                return None

            if value is not None:
                memory.value = value

            if importance is not None:
                memory.importance = importance

            memory.updated_at = datetime.utcnow()

            session.commit()
            session.refresh(memory)

            return memory

    def delete_memory_by_id(
        self,
        user_id: int,
        memory_id: int,
    ) -> bool:
        with self.SessionLocal() as session:
            memory = session.scalar(
                select(Memory).where(
                    Memory.memory_id == memory_id,
                    Memory.user_id == user_id,
                )
            )

            if memory is None:
                return False

            session.delete(memory)
            session.commit()

            return True

    # ------------------------------------------------------------------
    # Existing memory / conversation / reminder methods
    # ------------------------------------------------------------------

    def get_last_interaction_id(
        self,
        conversation_id: int,
    ) -> str | None:
        with self.SessionLocal() as session:
            conversation = session.get(
                Conversation,
                conversation_id,
            )

            if conversation is None:
                return None

            return conversation.last_interaction_id

    def delete_memory(
        self,
        user_id: int,
        key: str,
    ) -> bool:
        with self.SessionLocal() as session:
            memory = session.scalars(
                select(Memory)
                .where(
                    Memory.user_id == user_id,
                    Memory.key == key,
                )
            ).first()

            if memory is None:
                return False

            session.delete(memory)
            session.commit()

            return True

    def create_reminder(
        self,
        user_id: int,
        channel_id: int,
        message: str,
        remind_at: datetime,
    ) -> Reminder:
        with self.SessionLocal() as session:
            reminder = Reminder(
                user_id=user_id,
                channel_id=channel_id,
                message=message,
                remind_at=remind_at,
                completed=False,
                created_at=datetime.utcnow(),
            )

            session.add(reminder)
            session.commit()
            session.refresh(reminder)

            return reminder

    def get_due_reminders(
        self,
        now: datetime,
    ) -> list[Reminder]:
        with self.SessionLocal() as session:
            reminders = session.scalars(
                select(Reminder)
                .where(
                    Reminder.completed.is_(False),
                    Reminder.remind_at <= now,
                )
                .order_by(Reminder.remind_at.asc())
            ).all()

            return list(reminders)

    def complete_reminder(
        self,
        reminder_id: int,
    ) -> bool:
        with self.SessionLocal() as session:
            reminder = session.get(
                Reminder,
                reminder_id,
            )

            if reminder is None:
                return False

            reminder.completed = True

            session.commit()

            return True

    def get_pending_reminders(
        self,
        user_id: int,
    ) -> list[Reminder]:
        with self.SessionLocal() as session:
            reminders = session.scalars(
                select(Reminder)
                .where(
                    Reminder.user_id == user_id,
                    Reminder.completed.is_(False),
                )
                .order_by(Reminder.remind_at.asc())
            ).all()

            return list(reminders)
