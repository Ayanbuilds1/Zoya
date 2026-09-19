import re


class MemoryExtractor:
    """
    Extract simple, high-confidence long-term memories from user messages.

    Important safety rule:
    Questions must never be treated as facts.

    Examples:
        "Mera naam Ayan hai" -> save name=Ayan
        "Mera naam kya hai?" -> save nothing
        "Mera favourite color black hai" -> save favorite_color=black
        "Mera favourite color kya hai?" -> save nothing
    """

    QUESTION_WORDS = {
        "kya",
        "kaun",
        "kon",
        "kaunsa",
        "kaunsi",
        "kaise",
        "kyun",
        "kyon",
        "kab",
        "kahan",
        "kidhar",
        "what",
        "who",
        "which",
        "why",
        "when",
        "where",
        "how",
    }

    def _clean_value(self, value: str) -> str:
        return re.sub(r"\s+", " ", value.strip(" .!?,;:"))

    def _is_valid_value(self, value: str) -> bool:
        """
        Reject obvious question/placeholder values such as:
        "kya", "what", "kaunsa", etc.
        """
        cleaned = self._clean_value(value)

        if not cleaned:
            return False

        if "?" in value:
            return False

        words = re.findall(r"[A-Za-z]+", cleaned.lower())

        if not words:
            return False

        if cleaned.lower() in self.QUESTION_WORDS:
            return False

        if any(word in self.QUESTION_WORDS for word in words):
            return False

        return True

    def _looks_like_question(self, text: str) -> bool:
        """
        Detect common question forms before saving explicit memories.
        """
        normalized = text.strip().lower()

        if "?" in normalized:
            return True

        question_patterns = [
            r"^\s*kya\b",
            r"^\s*kaun\b",
            r"^\s*kon\b",
            r"^\s*kaunsa\b",
            r"^\s*kaunsi\b",
            r"^\s*kaise\b",
            r"^\s*kyun\b",
            r"^\s*kyon\b",
            r"^\s*kab\b",
            r"^\s*kahan\b",
            r"^\s*kidhar\b",
            r"^\s*what\b",
            r"^\s*who\b",
            r"^\s*which\b",
            r"^\s*why\b",
            r"^\s*when\b",
            r"^\s*where\b",
            r"^\s*how\b",
        ]

        return any(
            re.search(pattern, normalized, re.IGNORECASE)
            for pattern in question_patterns
        )

    def extract(self, message: str) -> list[dict]:
        memories: list[dict] = []
        text = message.strip()

        if not text:
            return memories

        # ---------------------------------------------------------
        # Name
        # ---------------------------------------------------------
        name_patterns = [
            r"\bmera naam ([A-Za-z][A-Za-z .'-]{1,50}) hai\b",
            r"\bmy name is ([A-Za-z][A-Za-z .'-]{1,50})\b",
        ]

        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)

            if match:
                value = self._clean_value(match.group(1))

                if self._is_valid_value(value):
                    memories.append(
                        {
                            "category": "personal",
                            "key": "name",
                            "value": value,
                            "importance": 10,
                            "confidence": 1.0,
                            "source": "conversation",
                        }
                    )
                break

        # ---------------------------------------------------------
        # Communication language
        # ---------------------------------------------------------
        language_patterns = [
            r"\bmujhe (hinglish|hindi|english) mein reply kar(?:na|o)\b",
            r"\breply (?:to me )?in (hinglish|hindi|english)\b",
        ]

        for pattern in language_patterns:
            match = re.search(pattern, text, re.IGNORECASE)

            if match and not self._looks_like_question(text):
                memories.append(
                    {
                        "category": "instruction",
                        "key": "communication_language",
                        "value": match.group(1).lower(),
                        "importance": 9,
                        "confidence": 1.0,
                        "source": "conversation",
                    }
                )
                break

        # ---------------------------------------------------------
        # Likes
        # ---------------------------------------------------------
        like_patterns = [
            r"\bmujhe (.+?) pasand hai\b",
            r"\bi like (.+?)(?:[.!?]|$)",
        ]

        for pattern in like_patterns:
            match = re.search(pattern, text, re.IGNORECASE)

            if match:
                value = self._clean_value(match.group(1))

                if self._is_valid_value(value):
                    memories.append(
                        {
                            "category": "preference",
                            "key": "likes",
                            "value": value,
                            "importance": 6,
                            "confidence": 0.85,
                            "source": "conversation",
                        }
                    )
                break

        # ---------------------------------------------------------
        # Favorite color
        # ---------------------------------------------------------
        color_patterns = [
            r"\bmera favourite color ([a-zA-Z][a-zA-Z -]{0,30}) hai\b",
            r"\bmera favorite color ([a-zA-Z][a-zA-Z -]{0,30}) hai\b",
            r"\bmy favorite color is ([a-zA-Z][a-zA-Z -]{0,30})\b",
        ]

        for pattern in color_patterns:
            match = re.search(pattern, text, re.IGNORECASE)

            if match:
                value = self._clean_value(match.group(1))

                if self._is_valid_value(value):
                    memories.append(
                        {
                            "category": "preference",
                            "key": "favorite_color",
                            "value": value.lower(),
                            "importance": 6,
                            "confidence": 1.0,
                            "source": "conversation",
                        }
                    )
                break

        # ---------------------------------------------------------
        # Explicit memory
        # ---------------------------------------------------------
        remember_patterns = [
            r"\byaad rakho(?: ki)? (.+)",
            r"\bremember(?: that)? (.+)",
        ]

        for pattern in remember_patterns:
            match = re.search(pattern, text, re.IGNORECASE)

            if match:
                value = self._clean_value(match.group(1))

                if self._looks_like_question(value):
                    break

                # If the same message already produced a structured
                # memory, do not also create a generic explicit_memory.
                structured_keys = {
                    item["key"]
                    for item in memories
                    if item["key"]
                    in {
                        "name",
                        "communication_language",
                        "likes",
                        "favorite_color",
                    }
                }

                if structured_keys:
                    break

                if self._is_valid_value(value):
                    memories.append(
                        {
                            "category": "fact",
                            "key": "explicit_memory",
                            "value": value,
                            "importance": 8,
                            "confidence": 1.0,
                            "source": "manual",
                        }
                    )

                break

        return memories