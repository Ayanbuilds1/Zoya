"""Lightweight, provider-independent extraction of durable user memories.

This is deliberately a small semantic normalizer, not a command grammar. It
recognises durable concepts and common Hinglish/English expressions, then
returns the generic memory records used by the existing database and UI.
"""

from __future__ import annotations

import re


class MemoryExtractor:
    QUESTION_WORDS = {
        "kya", "kaun", "kon", "kaunsa", "kaunsi", "kaise", "kyun",
        "kyon", "kab", "kahan", "kidhar", "what", "who", "which",
        "why", "when", "where", "how",
    }

    STRUCTURED_KEYS = {
        "name", "communication_language", "addressing_style",
        "favorite_game", "favorite_sport", "favorite_color",
        "greeting_style",
    }

    _FAVORITE_KINDS = {
        "game": "favorite_game",
        "khel": "favorite_game",
        "sport": "favorite_sport",
    }

    def _clean_value(self, value: str) -> str:
        return re.sub(r"\s+", " ", value.strip(" .!?,;:"))

    def _normalise(self, text: str) -> str:
        return " ".join(self._clean_value(text).casefold().split())

    def _is_valid_value(self, value: str) -> bool:
        cleaned = self._clean_value(value)
        if not cleaned or "?" in value:
            return False
        words = re.findall(r"[A-Za-z]+", cleaned.casefold())
        return bool(words) and not any(word in self.QUESTION_WORDS for word in words)

    def _looks_like_question(self, text: str) -> bool:
        normalized = self._normalise(text)
        return "?" in text or bool(re.match(
            r"^(?:kya|kaun|kon|kaunsa|kaunsi|kaise|kyun|kyon|kab|kahan|kidhar|what|who|which|why|when|where|how)\b",
            normalized,
        ))

    def _append_memory(self, memories: list[dict], *, category: str, key: str,
                       value: str, importance: int, confidence: float,
                       source: str) -> None:
        cleaned = self._clean_value(value)
        if not self._is_valid_value(cleaned):
            return
        candidate = {
            "category": category, "key": key, "value": cleaned,
            "importance": importance, "confidence": confidence, "source": source,
        }
        if not any(
            item["key"] == key and self._normalise(item["value"]) == self._normalise(cleaned)
            for item in memories
        ):
            memories.append(candidate)

    def _explicit_statement(self, text: str) -> str | None:
        """Return the fact being saved, never the save instruction itself."""
        patterns = (
            r"^(.*?)\s+(?:is\s*ko|isko|ise|isey|yeh|ye|this)\s+"
            r"(?:memory|mem(?:ory)?)\s*(?:me|mein|main)\s+(?:save|store)\b.*$",
            r"^(.*?)\s+(?:yaad\s+rakh(?:na|o|lo)|yaad\s+rakho)\b.*$",
            r"^remember(?:\s+that)?\s+(.+)$",
            r"^save\s+(?:this\s+)?(?:preference|memory)\s*[:,-]?\s*(.+)$",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            statement = self._clean_value(match.group(1))
            if statement and not self._looks_like_question(statement):
                return statement
        return None

    @staticmethod
    def _note_key(value: str) -> str:
        words = re.findall(r"[a-z0-9]+", value.casefold())[:6]
        return "note_" + "_".join(words or ["saved"])

    def _extract_structured(self, text: str, memories: list[dict], *, source: str) -> None:
        normalized = self._normalise(text)

        name = re.search(r"\b(?:mera naam|my name is)\s+([A-Za-z][A-Za-z .'-]{1,50}?)(?:\s+hai\b|$)", text, re.I)
        if name:
            self._append_memory(memories, category="personal", key="name", value=name.group(1),
                                importance=10, confidence=1.0, source=source)

        language = re.search(r"\b(hinglish|hindi|english)\b", normalized)
        if language and re.search(r"\b(reply|baat|bol|speak|talk|address)\b", normalized):
            self._append_memory(memories, category="instruction", key="communication_language",
                                value=language.group(1), importance=9, confidence=0.95, source=source)

        asks_for_aap = "aap" in normalized and (
            any(word in normalized for word in ("address", "respect", "bol", "baat", "use", "jagah"))
            or any(word in normalized for word in ("tu", "teri", "tera", "tujhe"))
        )
        if asks_for_aap:
            self._append_memory(memories, category="instruction", key="addressing_style",
                                value="respectful_aap", importance=10, confidence=0.98, source=source)

        favorite = re.search(
            r"\b(?:mera|my)\s+(?:fav(?:ourite)?|favorite)\s+"
            r"(game|sport|khel)\s+(.+?)(?:\s+(?:hai|is)\b|$)", text, re.I,
        )
        if favorite:
            kind = favorite.group(1).casefold()
            self._append_memory(memories, category="preference", key=self._FAVORITE_KINDS[kind],
                                value=favorite.group(2).casefold(), importance=7,
                                confidence=0.95, source=source)

        like = re.search(r"\bmujhe\s+(.+?)\s+pasand\s+hai\b|\bi\s+like\s+(.+?)(?:[.!?]|$)", text, re.I)
        if like:
            value = self._clean_value(like.group(1) or like.group(2)).casefold()
            if self._is_valid_value(value):
                self._append_memory(memories, category="preference",
                                    key="like_" + "_".join(re.findall(r"[a-z0-9]+", value)[:4]),
                                    value=value, importance=6, confidence=0.85, source=source)

        color = re.search(r"\b(?:mera|my)\s+(?:fav(?:ourite)?|favorite)\s+color\s+(.+?)(?:\s+(?:hai|is)\b|$)", text, re.I)
        if color:
            self._append_memory(memories, category="preference", key="favorite_color",
                                value=color.group(1).casefold(), importance=6, confidence=0.95, source=source)

    def extract(self, message: str) -> list[dict]:
        text = message.strip()
        if not text:
            return []

        memories: list[dict] = []
        explicit = self._explicit_statement(text)
        self._extract_structured(explicit or text, memories, source="manual" if explicit else "conversation")

        if explicit and not memories:
            self._append_memory(memories, category="fact", key=self._note_key(explicit), value=explicit,
                                importance=8, confidence=0.95, source="manual")

        return memories
