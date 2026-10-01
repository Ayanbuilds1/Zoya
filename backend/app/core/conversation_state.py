from __future__ import annotations

from dataclasses import dataclass, field
import re


@dataclass
class ConversationState:
    """Compact deterministic state for high-confidence multi-turn context."""

    topic: str = ""
    entities: dict[str, str] = field(default_factory=dict)
    last_user_message: str = ""
    last_correction: str = ""
    last_correction_value: str = ""
    pending_reference: str = ""
    recent_user_messages: list[str] = field(default_factory=list)


class ConversationStateTracker:
    """Track only high-confidence facts; leave open-ended meaning to Brain/LLM.

    The tracker deliberately avoids entity dictionaries, city lists, exact
    question/answer pairs, or topic-specific response rules. It answers only
    when the context is unambiguous and otherwise exposes compact state to the
    semantic Brain/final model.
    """

    _DESTINATION_PATTERNS = (
        re.compile(
            r"\b(?:main|mai|i\s+am|i'm|im|mujhe|mera)\s+"
            r"(?P<middle>[a-z][a-z0-9 .'-]{1,70}?)\s+"
            r"(?:jaana|jana|ja\s+(?:raha|rahi)(?:\s+hoon)?|going\s+to)\b",
            re.I,
        ),
        re.compile(
            r"\b(?:main|mai|mujhe|mera)\s+"
            r"(?P<middle>[a-z][a-z0-9 .'-]{1,70}?)\s+"
            r"ja\b",
            re.I,
        ),
    )
    _QUESTION_DESTINATION_RE = re.compile(
        r"\b(?:kahan|kaha|kidhar|where)\b.*\b(?:ja|jana|jaana|going|reaching|destination)\b",
        re.I,
    )
    _BUDGET_RE = re.compile(
        r"(?:\bbudget\b\s*(?:is|hai|ka|:)?\s*(?:rs\.?\s*)?|"
        r"\b(?:under|upto|up\s+to|around)\b\s*(?:rs\.?\s*)?|"
        r"₹\s*)(?P<amount>[0-9][0-9,]*(?:\.[0-9]+)?\s*(?:k|hazaar|thousand|lakh|lakhs)?)\b",
        re.I,
    )
    _BUDGET_TRAILING_RE = re.compile(
        r"\b(?P<amount>[0-9][0-9,]*(?:\.[0-9]+)?\s*(?:k|hazaar|thousand|lakh|lakhs)?)\s*"
        r"(?:ka|kaa|ke|ki|mein|me)?\s*\bbudget\b",
        re.I,
    )
    _PURPOSE_RE = re.compile(
        r"(?P<purpose>[a-z][a-z0-9 +#./'-]{1,40}?)\s+(?:ke\s+liye|for)\b",
        re.I,
    )
    _SHOPPING_SUBJECT_RE = re.compile(
        r"\b(?:mujhe|main|mai|i|i\s+want|i\s+need|looking\s+for|need)\s+"
        r"(?:ek|a|an|the)?\s*"
        r"(?P<subject>[a-z][a-z0-9 +#.'-]{1,40}?)\s+"
        r"(?:lena|lenna|buy|purchase|kharidna|chaahiye|chahiye)\b",
        re.I,
    )
    _SHOPPING_VERB_RE = re.compile(
        r"\b(?:buy|purchase|lena|lenna|kharidna|chahiye|chaahiye)\b",
        re.I,
    )
    _CORRECTION_START_RE = re.compile(
        r"^\s*(?:nahi|nahin|actually|i\s+mean|mera\s+matlab|not\s+that)\b"
        r"[,\s:;-]*(?P<body>.+)$",
        re.I,
    )
    _INLINE_NEGATION_RE = re.compile(r"\bnahi\b|\bnahin\b", re.I)
    _FRAMING_TAIL_RE = re.compile(
        r"\s+(?:bolna|bolne|kehna|kahne|matlab|mean|jaana|jana|going\s+to|hai|tha|thi|hoon|hun|hai na)\b.*$",
        re.I,
    )
    _TIME_PREFIX_RE = re.compile(
        r"^(?:(?:next|this|coming|last)\s+(?:week|month|year)|"
        r"(?:tomorrow|yesterday|today|kal|aaj)|"
        r"(?:next|this|coming)\s+[a-z]+)\s+",
        re.I,
    )
    _COMMON_PREFIX_RE = re.compile(
        r"^(?:ek|a|an|the|mera|meri|mere|mujhe|main|mai|i|i'm|im)\s+",
        re.I,
    )

    def __init__(self) -> None:
        self._states: dict[int, ConversationState] = {}

    def build(
        self,
        conversation_id: int,
        history: list[dict[str, str]],
    ) -> ConversationState:
        state = ConversationState()
        self._states[conversation_id] = state
        for item in history:
            if item.get("role") == "user":
                self._observe_text(state, item.get("content", ""))
        return state

    def get(self, conversation_id: int) -> ConversationState:
        return self._states.setdefault(conversation_id, ConversationState())

    def observe(
        self,
        conversation_id: int,
        message: str,
    ) -> ConversationState:
        state = self.get(conversation_id)
        self._observe_text(state, message)
        state.last_user_message = message.strip()
        state.recent_user_messages.append(message.strip())
        state.recent_user_messages = state.recent_user_messages[-8:]
        return state

    @staticmethod
    def _clean(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip(" .,!?:;\"'`"))

    @staticmethod
    def _is_question(text: str) -> bool:
        normalized = re.sub(r"\s+", " ", text.lower().strip())
        return bool(
            text.strip().endswith("?")
            or re.match(r"^(?:kya|kyu|kyun|kaise|kab|kahan|kaha|kidhar|what|why|how|when|where)\b", normalized)
        )

    @classmethod
    def _extract_destination_from_middle(cls, middle: str) -> str:
        value = cls._clean(middle)
        value = cls._TIME_PREFIX_RE.sub("", value)
        value = cls._COMMON_PREFIX_RE.sub("", value)
        if not value:
            return ""
        words = value.split()
        # Destination is the final short noun phrase before the travel verb.
        # Keep up to four words so names such as "New Delhi" remain intact.
        value = " ".join(words[-4:])
        value = cls._clean(value)
        if value.lower() in {"kahan", "kaha", "kidhar", "where"}:
            return ""
        return value

    @classmethod
    def _extract_destination_statement(cls, text: str) -> str:
        if cls._is_question(text):
            return ""
        for pattern in cls._DESTINATION_PATTERNS:
            match = pattern.search(text)
            if match:
                value = cls._extract_destination_from_middle(match.group("middle"))
                if value and len(value.split()) <= 4:
                    return value
        return ""

    @classmethod
    def _extract_destination_correction(cls, body: str) -> str:
        """Extract the replacement destination without any city-name list."""
        cleaned = cls._clean(body)
        if not cleaned or not cls._INLINE_NEGATION_RE.search(cleaned):
            return ""

        # Typical forms:
        #   Jaipur nahi, Udaipur jaana hai
        #   Pune nahi Nashik jaana hai
        #   old place nahi, new place bolna tha
        pieces = [cls._clean(piece) for piece in re.split(r",|\b(?:instead|rather)\b", cleaned, flags=re.I)]
        candidates: list[str] = []
        for index, piece in enumerate(pieces):
            if index == 0 and re.search(r"\bnahi\b|\bnahin\b", piece, flags=re.I):
                continue
            if re.search(r"\bnahi\b|\bnahin\b", piece, flags=re.I):
                continue
            if piece:
                candidates.append(piece)

        if not candidates:
            match = re.search(
                r"\b(?:nahi|nahin)\b\s*[,;:-]?\s*(.+)$",
                cleaned,
                flags=re.I,
            )
            if match:
                candidates.append(match.group(1))

        for candidate in reversed(candidates):
            value = cls._clean(cls._FRAMING_TAIL_RE.sub("", candidate))
            value = cls._clean(value)
            if not value:
                continue
            value = cls._extract_destination_from_middle(value)
            if value and value.lower() not in {"nahi", "nahin", "actually", "not that"}:
                return value
        return ""

    @classmethod
    def _extract_budget(cls, text: str) -> str:
        match = cls._BUDGET_RE.search(text) or cls._BUDGET_TRAILING_RE.search(text)
        if not match:
            return ""
        return cls._clean(match.group("amount"))

    @classmethod
    def _extract_purpose(cls, text: str) -> str:
        matches = list(
            re.finditer(
                r"(?P<purpose>[a-z][a-z0-9 +#./'-]{1,60}?)\s+(?:ke\s+liye|for)\b",
                text,
                flags=re.I,
            )
        )
        if not matches:
            return ""

        raw = cls._clean(matches[-1].group("purpose"))
        words = raw.split()
        if not words:
            return ""

        # Keep the final concise noun phrase immediately before the purpose
        # marker, then remove conversational scaffolding such as "main".
        words = words[-4:]
        while words and words[0].lower() in {
            "main", "mai", "i", "i'm", "im", "mujhe", "mujhko",
            "mera", "meri", "mere", "aur", "hai", "tha", "thi",
        }:
            words.pop(0)
        purpose = cls._clean(" ".join(words))
        if not purpose:
            return ""
        if purpose.lower() in {"mujhe", "main", "mera", "phone", "laptop", "camera"}:
            return ""
        return purpose

    @classmethod
    def _extract_subject(cls, text: str) -> str:
        match = cls._SHOPPING_SUBJECT_RE.search(text)
        if not match:
            return ""
        subject = cls._clean(match.group("subject"))
        subject = cls._TIME_PREFIX_RE.sub("", subject)
        # In phrases like "photography ke liye phone lena hai", keep the
        # actual object (phone). In "photography ke liye lena hai", there is
        # no new object, so do not switch the active topic.
        if re.search(r"\bke\s+liye\b|\bfor\b", subject, flags=re.I):
            tail = re.split(r"\bke\s+liye\b|\bfor\b", subject, maxsplit=1, flags=re.I)[-1]
            subject = cls._clean(tail)
        return subject

    @staticmethod
    def _is_preference_or_meta_message(normalized: str) -> bool:
        markers = (
            "answer",
            "answers",
            "response",
            "responses",
            "textbook",
            "natural",
            "style",
            "mat use",
            "don't use",
            "do not use",
            "avoid",
            "roman hinglish",
            "devanagari",
        )
        return normalized.startswith(("mujhe ", "please ", "from now", "aage se")) and any(
            marker in normalized for marker in markers
        )

    def _observe_text(self, state: ConversationState, message: str) -> None:
        text = self._clean(message)
        if not text:
            return
        normalized = text.lower()

        is_question = self._is_question(text)
        correction_match = self._CORRECTION_START_RE.match(text)
        if correction_match:
            state.last_correction = text

        destination_correction = ""
        if correction_match:
            destination_correction = self._extract_destination_correction(
                correction_match.group("body")
            )

        destination = "" if is_question else self._extract_destination_statement(text)
        budget = self._extract_budget(text)
        purpose = self._extract_purpose(text)
        subject = self._extract_subject(text)

        # A correction is field-specific. Never interpret "Actually budget..."
        # as a destination correction merely because a destination exists.
        if destination_correction:
            destination = destination_correction
        elif correction_match and not (destination or budget or purpose or subject):
            destination = ""

        # Explicit new subject switches the active topic and prevents stale
        # entities from another topic from leaking into the new one.
        new_topic = ""
        if destination:
            new_topic = "travel/destination"
        elif subject:
            new_topic = f"shopping/{subject.lower()}"

        if new_topic and state.topic and new_topic != state.topic:
            state.entities.clear()

        if new_topic:
            state.topic = new_topic

        if destination:
            state.entities["destination"] = destination
            if correction_match:
                state.last_correction_value = destination
        if budget:
            state.entities["budget"] = budget
            if correction_match:
                state.last_correction_value = budget
        if purpose:
            state.entities["purpose"] = purpose.lower()
            if correction_match:
                state.last_correction_value = purpose.lower()
        if subject and not state.topic:
            state.topic = f"shopping/{subject.lower()}"

        # A pure preference/meta turn must never wipe the active context.
        if self._is_preference_or_meta_message(normalized):
            state.pending_reference = ""
            return

        if any(
            marker in normalized
            for marker in (
                "what about",
                "aur ",
                "also ",
                "same ",
                "phir ",
                "wahi ",
                "yeh ",
                "ye ",
                "isko ",
                "iske ",
                "usko ",
                "uske ",
            )
        ):
            state.pending_reference = text
        else:
            state.pending_reference = ""

        state.last_user_message = text

    @classmethod
    def _extract_correction_value(cls, body: str) -> str:
        """Return the newest replacement phrase from a correction."""
        cleaned = cls._clean(body)
        if not cleaned:
            return ""
        destination = cls._extract_destination_correction(cleaned)
        if destination:
            return destination
        budget = cls._extract_budget(cleaned)
        if budget:
            return budget
        purpose = cls._extract_purpose(cleaned)
        if purpose:
            return purpose
        return ""

    @staticmethod
    def acknowledge_state_statement(
        message: str,
        state: ConversationState,
    ) -> str | None:
        """Acknowledge a clear destination statement without adding advice."""
        normalized = re.sub(r"\s+", " ", message.lower().strip())
        destination = state.entities.get("destination")
        if not destination or ConversationStateTracker._is_question(message):
            return None
        if re.search(
            r"\b(?:main|mai|i am|i'm|im|mujhe|mera)\b.*\b(?:jaana|jana|ja raha|ja rahi|going)\b",
            normalized,
        ):
            return f"Theek hai, tum {destination} ja rahe ho."
        return None

    @staticmethod
    def acknowledge_correction(
        message: str,
        state: ConversationState,
    ) -> str | None:
        normalized = re.sub(r"\s+", " ", message.lower().strip())
        if not state.last_correction or not normalized.startswith(
            ("nahi", "nahin", "actually", "i mean", "mera matlab", "not that")
        ):
            return None

        destination = state.entities.get("destination")
        if destination:
            return f"Theek hai, ab {destination} wala update follow karungi."

        # Multi-attribute shopping refinements should continue through Brain +
        # the final provider so the answer can act on the complete update
        # (for example budget + photography), rather than stopping at a bare ack.
        purpose = state.entities.get("purpose")
        shopping_refinement = bool(
            purpose
            and state.topic.startswith("shopping/")
            and ConversationStateTracker._SHOPPING_VERB_RE.search(message)
        )
        if shopping_refinement:
            return None

        budget = state.entities.get("budget")
        if budget:
            return f"Theek hai, budget ab {budget} hai."
        if purpose:
            return f"Theek hai, ab purpose {purpose} hai."
        return "Samajh gayi. Latest correction note kar li."

    @staticmethod
    def resolve(message: str, state: ConversationState) -> str | None:
        normalized = re.sub(r"\s+", " ", message.lower().strip())

        destination = state.entities.get("destination")
        if destination and ConversationStateTracker._QUESTION_DESTINATION_RE.search(normalized):
            return destination

        if destination and normalized in {
            "mera destination kya hai",
            "my destination kya hai",
            "what is my destination",
        }:
            return destination

        budget = state.entities.get("budget")
        if budget and re.fullmatch(
            r"(?:mera\s+)?budget\s+(?:kya\s+(?:tha|hai)|kitna\s+(?:tha|hai))|what\s+was\s+my\s+budget",
            normalized,
        ):
            return budget

        return None

    @staticmethod
    def focused_history(
        history: list[dict[str, str]],
        current_message: str,
        max_messages: int = 6,
    ) -> list[dict[str, str]]:
        """Keep the recent conversational window used by semantic reasoning."""
        if not history:
            return []
        items = [
            {
                "role": item.get("role", ""),
                "content": str(item.get("content", "")).strip(),
            }
            for item in history
            if item.get("role") in {"user", "assistant"}
            and str(item.get("content", "")).strip()
        ]
        return items[-max_messages:]

    @classmethod
    def resolve_from_history(
        cls,
        history: list[dict[str, str]],
        current_message: str,
    ) -> str | None:
        """Rebuild high-confidence state from persisted history."""
        tracker = cls()
        state = tracker.build(-1, history)
        return tracker.resolve(current_message, state)

    def prompt_context(self, conversation_id: int | None) -> str:
        if conversation_id is None:
            return "(No deterministic conversation state available.)"
        state = self.get(conversation_id)
        lines: list[str] = []
        if state.topic:
            lines.append(f"active_topic: {state.topic}")
        for key, value in state.entities.items():
            lines.append(f"{key}: {value}")
        if state.last_correction:
            lines.append(f"last_correction: {state.last_correction}")
        if state.pending_reference:
            lines.append(f"pending_reference: {state.pending_reference}")
        if not lines:
            return "(No deterministic conversation state available.)"
        return "\n".join(lines)
