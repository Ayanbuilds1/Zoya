from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import get_close_matches


@dataclass(frozen=True)
class NLPFeatures:
    """Lightweight local NLP analysis for Zoya.

    This layer intentionally runs without an external model. It performs
    normalization, tokenization, script/language-style detection, question and
    follow-up detection, correction detection, preference extraction and
    response-shape cues before the Brain/final model runs.
    """

    original: str
    normalized: str
    tokens: tuple[str, ...]
    script: str
    language_style: str
    is_question: bool
    question_type: str
    is_contextual_follow_up: bool
    is_correction: bool
    needs_current_information: bool
    explicit_research: bool
    wants_detail: bool
    wants_concise: bool
    wants_comparison: bool
    asks_for_code: bool
    preference_instruction: bool
    preferences: dict[str, str] = field(default_factory=dict)
    is_preference_only: bool = False
    avoid_words: tuple[str, ...] = ()
    topic_terms: tuple[str, ...] = ()


class ZoyaNLP:
    """Rule-based NLP layer designed for Roman Hinglish + English chat."""

    HINDI_CUES = {
        "hai", "hain", "ho", "hua", "hoge", "mujhe", "mera", "meri",
        "mere", "tum", "tumhe", "tumhara", "aap", "aapko", "kya", "kyu",
        "kyun", "kaise", "kab", "kahan", "batao", "bata", "kar", "karo",
        "karna", "chahiye", "nahi", "nahin", "acha", "accha", "aur", "ye",
        "wo", "iska", "uska", "isme", "ismein", "phir", "abhi", "jaise",
        "sirf", "thoda", "thodi", "bahut", "bilkul", "mat", "bolo", "bol",
    }

    CONTEXT_MARKERS = {
        "aur", "also", "and", "phir", "same", "same one", "same topic", "wahi",
        "ye", "yeh", "wo", "woh", "isko", "ispe", "isme", "usko", "uspe",
        "iske", "uske", "continue", "more", "details", "detail", "again",
    }

    CURRENT_MARKERS = {
        "latest", "current", "today", "today's", "recent", "recently", "abhi",
        "currently", "this week", "this month", "right now", "aaj", "now",
        "latest update", "latest updates", "current update", "current updates",
    }

    RESEARCH_MARKERS = {
        "research", "web research", "web search", "search online", "search the web",
        "verify", "verify online", "fact check", "fact-check", "sources", "source",
        "internet pe check", "online check", "online search",
    }

    DETAIL_MARKERS = (
        "detail me", "details me", "detail mein", "details mein", "detailed",
        "deeply", "deep dive", "explain properly", "properly explain",
        "step by step", "step-by-step", "full explain", "pura explain",
        "properly batao", "proper explain",
    )

    CONCISE_MARKERS = (
        "short answer", "in short", "one line", "briefly", "brief answer",
        "short me", "short mein", "sirf short", "just tell me",
    )

    COMPARISON_MARKERS = (
        "compare", "comparison", "difference", "difference between", "vs", "versus",
        "better than", "farak", "compare karo",
    )

    CODE_MARKERS = (
        "code", "coding", "function", "snippet", "program", "script", "syntax",
        "python", "javascript", "java", "html", "css", "sql", "bash", "shell",
        "json", "yaml", "typescript", "react", "django", "node.js", "nodejs",
    )

    PREFERENCE_HINTS = (
        "prefer", "preference", "mat use", "don't use", "do not use", "avoid",
        "use karo", "use mat karo", "bolo", "bolna", "address", "style me",
        "roman", "hinglish", "gen z", "gen-z", "devanagari",
    )

    _TOKEN_RE = re.compile(r"[A-Za-z0-9_]+(?:['’.-][A-Za-z0-9_]+)*|[^\w\s]", re.UNICODE)
    _QUOTE_RE = re.compile(r"[\"'“”‘’`]+([^\"'“”‘’`]+?)[\"'“”‘’`]+")
    _AVOID_WORDS_RE = re.compile(
        r"(?P<words>[^\n]{1,160}?)\s+words?\s+(?:bilkul\s+)?(?:mat\s+use\s+karo|use\s+mat\s+karo|don't\s+use|do\s+not\s+use|avoid)",
        re.IGNORECASE,
    )
    _AVOID_SINGLE_RE = re.compile(
        r"(?:word|term)\s*[=:]?\s*[\"'“”‘’`]?([^\"'“”‘’`?.,;]+?)[\"'“”‘’`]?\s*(?:mat\s+use|don't\s+use|do\s+not\s+use|avoid)",
        re.IGNORECASE,
    )

    def analyze(
        self,
        text: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> NLPFeatures:
        original = (text or "").strip()
        normalized = self.normalize(original)
        tokens = tuple(self.tokenize(normalized))
        script = self.detect_script(original)
        language_style = self.detect_language_style(normalized, tokens, script)
        question_type = self.detect_question_type(normalized)
        is_question = "?" in original or question_type != "statement"
        contextual = self.is_contextual_follow_up(normalized)
        correction = self.is_correction(normalized)
        current = self.has_marker(normalized, self.CURRENT_MARKERS)
        research = self.has_marker(normalized, self.RESEARCH_MARKERS)
        detail = self.has_any(normalized, self.DETAIL_MARKERS)
        concise = self.has_any(normalized, self.CONCISE_MARKERS)
        comparison = self.has_any(normalized, self.COMPARISON_MARKERS)
        asks_code = self.has_any(normalized, self.CODE_MARKERS) and (
            "code" in normalized
            or "example" in normalized
            or "function" in normalized
            or "program" in normalized
            or normalized.startswith(("python", "javascript", "java", "html", "css", "sql", "json"))
        )
        preferences, avoid_words = self.extract_preferences(original, normalized)
        preference_instruction = bool(preferences or avoid_words)
        preference_only = self.is_preference_only_message(
            normalized=normalized,
            preference_instruction=preference_instruction,
            is_question=is_question,
            is_contextual_follow_up=contextual,
            correction=correction,
            needs_current_information=current,
            explicit_research=research,
            wants_detail=detail,
            wants_comparison=comparison,
            asks_for_code=asks_code,
        )
        topic_terms = self._topic_terms(tokens)

        # A message is more likely to be contextual when it has an incomplete
        # continuation marker and there is prior conversation available.
        if contextual and conversation_history:
            contextual = True

        return NLPFeatures(
            original=original,
            normalized=normalized,
            tokens=tuple(tokens),
            script=script,
            language_style=language_style,
            is_question=is_question,
            question_type=question_type,
            is_contextual_follow_up=contextual,
            is_correction=correction,
            needs_current_information=current,
            explicit_research=research,
            wants_detail=detail,
            wants_concise=concise,
            wants_comparison=comparison,
            asks_for_code=asks_code,
            preference_instruction=preference_instruction,
            preferences=preferences,
            is_preference_only=preference_only,
            avoid_words=tuple(avoid_words),
            topic_terms=tuple(topic_terms),
        )

    @staticmethod
    def normalize(text: str) -> str:
        text = (text or "").replace("’", "'").replace("“", '"').replace("”", '"')
        text = re.sub(r"\s+", " ", text.strip().lower())
        return text

    def tokenize(self, text: str) -> list[str]:
        return [token for token in self._TOKEN_RE.findall(text) if token.strip()]

    @staticmethod
    def detect_script(text: str) -> str:
        devanagari = sum(1 for ch in text if "\u0900" <= ch <= "\u097f")
        latin = sum(1 for ch in text if ("a" <= ch.lower() <= "z"))
        if devanagari and latin:
            return "mixed"
        if devanagari:
            return "devanagari"
        if latin:
            return "latin"
        return "unknown"

    def detect_language_style(self, normalized: str, tokens: tuple[str, ...], script: str) -> str:
        if script == "devanagari":
            return "hindi_devanagari"
        token_words = [t for t in tokens if re.search(r"[a-z]", t)]
        hindi_hits = sum(1 for token in token_words if token in self.HINDI_CUES)
        if script == "latin" and hindi_hits:
            return "roman_hinglish"
        return "english" if script == "latin" else "unknown"

    def detect_question_type(self, normalized: str) -> str:
        if not normalized:
            return "statement"
        patterns = (
            ("what", ("what is", "what are", "what's", "kya hai", "kya hota hai")),
            ("who", ("who is", "who are", "kaun hai", "kon hai")),
            ("why", ("why", "kyu", "kyun", "kyon")),
            ("how", ("how", "kaise", "how much", "how many", "kitna", "kitne")),
            ("when", ("when", "kab")),
            ("where", ("where", "kahan", "kidhar")),
        )
        for kind, phrases in patterns:
            if normalized.startswith(phrases):
                return kind
        return "question" if normalized.endswith("?") else "statement"

    @classmethod
    def is_contextual_follow_up(cls, normalized: str) -> bool:
        if not normalized:
            return False
        words = normalized.split()
        if len(words) > 12:
            return False
        if normalized.startswith(("aur ", "also ", "and ", "phir ", "same ", "wahi ", "ye ", "yeh ", "wo ", "woh ")):
            return True
        if normalized.endswith((" bhi?", " bhi")) and len(words) <= 8:
            return True
        compact_markers = ("isko", "ispe", "isme", "usko", "uspe", "iske", "uske", "continue", "more", "details", "detail")
        return any(normalized == m or normalized.startswith(m + " ") for m in compact_markers)

    @classmethod
    def is_correction(cls, normalized: str) -> bool:
        markers = ("nahi mera matlab", "nahi matlab", "i mean", "actually", "not that", "mera matlab", "maine bola", "mene bola")
        return any(normalized.startswith(m) or m in normalized[:60] for m in markers)


    @staticmethod
    def is_preference_only_message(
        *,
        normalized: str,
        preference_instruction: bool,
        is_question: bool,
        is_contextual_follow_up: bool,
        correction: bool,
        needs_current_information: bool,
        explicit_research: bool,
        wants_detail: bool,
        wants_comparison: bool,
        asks_for_code: bool,
    ) -> bool:
        """Return True when the message changes response behavior but asks no content question."""
        if not preference_instruction:
            return False
        if is_question or is_contextual_follow_up or correction:
            return False
        if needs_current_information or explicit_research or wants_detail or wants_comparison or asks_for_code:
            return False

        preference_markers = (
            "mujhe", "main chahta", "main chahti", "prefer", "preference",
            "mat use", "avoid", "don't use", "do not use", "natural",
            "textbook", "roman", "hinglish", "devanagari", "gen z",
            "gen-z", "genz", "tum use karo", "aise bolo", "waise bolo",
            "answer style", "response style",
        )
        return any(marker in normalized for marker in preference_markers)

    @staticmethod
    def has_marker(normalized: str, markers: set[str]) -> bool:
        return any(marker in normalized for marker in markers)

    @staticmethod
    def has_any(normalized: str, markers: tuple[str, ...]) -> bool:
        return any(marker in normalized for marker in markers)

    def extract_preferences(self, original: str, normalized: str) -> tuple[dict[str, str], list[str]]:
        preferences: dict[str, str] = {}
        avoid_words: list[str] = []

        if "devanagari" in normalized and ("hinglish" in normalized or "roman" in normalized or "genz" in normalized or "gen-z" in normalized):
            preferences["communication_language"] = "Roman Hinglish (Latin script); do not use Devanagari"
        elif "roman hinglish" in normalized or "roman/latin" in normalized:
            preferences["communication_language"] = "Roman Hinglish (Latin script)"
        elif "hinglish" in normalized and any(x in normalized for x in ("bolo", "bolna", "response", "reply", "answer")):
            preferences["communication_language"] = "Roman Hinglish"

        if re.search(r"\btum(?:se)?\s+(?:bolo|baat|address|use)\b|\bmujhe\s+tum\b|\btum\s+use\s+karo\b", normalized):
            preferences["addressing_style"] = "tum"

        if "gen z" in normalized or "gen-z" in normalized or "genz" in normalized:
            if "hinglish" in normalized:
                preferences["response_style"] = "natural Gen-Z conversational Roman Hinglish"
            else:
                preferences["response_style"] = "natural Gen-Z conversational style"

        if any(phrase in normalized for phrase in (
            "textbook jaisa mat",
            "textbook jaisa nahi",
            "textbook ki tarah mat",
            "natural rakho",
            "natural answer",
            "naturally bolo",
            "natural tareeke se",
        )):
            preferences["response_style"] = (
                "natural conversational style; avoid textbook-like or overly formal phrasing"
            )

        for match in self._QUOTE_RE.findall(original):
            if any(term in normalized for term in ("avoid", "don't use", "do not use", "mat use", "use mat")):
                self._add_avoid_terms(match, avoid_words)

        for match in self._AVOID_WORDS_RE.finditer(original):
            self._add_avoid_terms(match.group("words"), avoid_words)

        # Natural unquoted form: "mahatvapurna, udaharan, jaise words mat use karo"
        marker = re.search(r"([^\n]{1,140}?)\s+words?\s+(?:bilkul\s+)?(?:mat\s+use\s+karo|use\s+mat\s+karo)", original, re.IGNORECASE)
        if marker:
            candidate = marker.group(1).strip(" -:;,.\"")
            # Keep only the likely list after common cue phrases.
            for prefix in ("fir se answer do", "answer do", "please", "plz"):
                candidate = re.sub(rf"\s+{re.escape(prefix)}.*$", "", candidate, flags=re.IGNORECASE).strip()
            self._add_avoid_terms(candidate, avoid_words)

        # Single explicit term form: "word: foo mat use karo"
        for match in re.finditer(r"(?:word|term)\s*[:=]\s*[\"'`]?([^\"'`\n?]+?)[\"'`]?(?:\s+mat\s+use|\s+don't\s+use|\s+do\s+not\s+use|\s+avoid)", original, re.IGNORECASE):
            self._add_avoid_terms(match.group(1), avoid_words)

        return preferences, self._unique(avoid_words)

    @staticmethod
    def _add_avoid_terms(raw: str, out: list[str]) -> None:
        raw = re.sub(r"\b(?:words|word|terms|term)\b", "", raw, flags=re.IGNORECASE)
        raw = raw.strip(" ,;:.-\"'`")
        if not raw:
            return
        parts = re.split(r"\s*,\s*|\s+and\s+|\s+aur\s+", raw, flags=re.IGNORECASE)
        for part in parts:
            part = part.strip(" ,;:.-\"'`").lower()
            if 1 <= len(part) <= 50 and re.search(r"[a-z]", part):
                out.append(part)

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value not in seen:
                seen.add(value)
                result.append(value)
        return result

    @staticmethod
    def _topic_terms(tokens: tuple[str, ...]) -> list[str]:
        stop = {"what", "is", "are", "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "hai", "kya", "kaise", "aur", "me", "mein", "please", "pls"}
        return [token for token in tokens if re.search(r"[a-z]", token) and len(token) > 2 and token not in stop][:12]

    @staticmethod
    def suggest_token_correction(token: str, vocabulary: list[str], cutoff: float = 0.86) -> str:
        """Return a high-confidence typo correction without changing semantics."""
        matches = get_close_matches(token.lower(), [v.lower() for v in vocabulary], n=1, cutoff=cutoff)
        return matches[0] if matches else token
