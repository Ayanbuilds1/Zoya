from __future__ import annotations

import json
import re
from typing import Any


def _load_avoid_words(memory_manager: Any, user_id: int) -> list[str]:
    values: list[str] = []
    for memory in memory_manager.get_memories(user_id=user_id, min_importance=8):
        if memory.key != "response_avoid_words":
            continue
        try:
            raw = json.loads(memory.value)
            if isinstance(raw, list):
                values.extend(str(x).strip() for x in raw if str(x).strip())
        except (TypeError, ValueError, json.JSONDecodeError):
            if str(memory.value).strip():
                values.append(str(memory.value).strip())
    return values


COMMON_SYNONYMS = {
    "mahatvapurna": "important",
    "mahatvapurn": "important",
    "udaharan": "example",
    "suvidha": "feature",
    "anumati": "permission",
    "pramukh": "main",
    "avashyak": "needed",
    "anuprayog": "app",
}


def _replace_avoid_word(text: str, term: str) -> str:
    replacement = COMMON_SYNONYMS.get(term.lower(), "")
    pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE)
    return pattern.sub(replacement, text)


def _sanitize_unverified_research_claims(text: str, research_available: bool) -> str:
    if research_available:
        return text
    replacements = {
        r"\bresearch ke mutabik\b": "aam taur par",
        r"\bresearch ke according\b": "aam taur par",
        r"\baccording to (?:research|studies)\b": "generally",
        r"\bresearch shows that\b": "generally",
        r"\bstudies show that\b": "generally",
        r"\bmaine (?:ek )?(?:article|report|study) padha(?: hai| tha)?\b": "ek common point ye hai",
        r"\bmaine research ki\b": "available information ke basis par",
    }
    cleaned = text
    for pattern, replacement in replacements.items():
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    return cleaned


def _remove_inline_copy_label(text: str) -> str:
    # Some models emit labels such as `jsonCopy` before a fenced block.
    return re.sub(r"(?im)^\s*(?:json|python|javascript|typescript|html|css|sql|bash|shell)copy\s*$\n", "", text)


def _looks_like_internal_leak(text: str, user_message: str) -> bool:
    request = user_message.lower()
    explicit_code_request = any(x in request for x in ("source code", "backend code", "implementation", "show me the code", "code of zoya", "chat.py", "provider.py"))
    if explicit_code_request:
        return False
    markers = (
        "self.send_message(",
        "conversation_history=",
        "build_contextual_message(",
        "BrainDecision(",
        "create_ai_provider(",
        "ZOYA_SYSTEM_INSTRUCTION",
    )
    return any(marker in text for marker in markers)


def sanitize_response(
    reply: str,
    *,
    user_id: int,
    memory_manager: Any,
    research_available: bool,
    user_message: str,
) -> str:
    text = (reply or "").strip()
    if not text:
        return text

    text = _remove_inline_copy_label(text)
    text = _sanitize_unverified_research_claims(text, research_available)

    for term in _load_avoid_words(memory_manager, user_id):
        if len(term) >= 2:
            text = _replace_avoid_word(text, term)

    # Never leak backend implementation snippets into a normal user answer.
    if _looks_like_internal_leak(text, user_message):
        text = (
            "Main is request ko direct answer ke form me explain karungi, "
            "internal implementation details nahi dungi."
        )

    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
