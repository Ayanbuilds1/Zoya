from dataclasses import dataclass


@dataclass(frozen=True)
class IntentDecision:
    """
    Result of Zoya's deterministic intent routing.
    """

    intent: str
    handled: bool = False
    response: str | None = None


class ZoyaIntentRouter:
    """
    Lightweight deterministic intent router.

    This router handles high-confidence computer-control intents
    before the AI provider is called.

    The purpose is to prevent the LLM from turning a direct request
    about Zoya's own PC-control capability into a generic automation
    tutorial.
    """

    AUTOMATION_TERMS = (
        "automation",
        "automate",
        "automating",
        "automated",
        "automation kar",
        "automate karo",
        "automate karna",
    )

    COMPUTER_TERMS = (
        "pc",
        "computer",
        "windows pc",
        "windows computer",
        "desktop",
        "laptop",
        "machine",
    )

    CONTROL_TERMS = (
        "control",
        "use kar",
        "use karna",
        "use karo",
        "operate",
        "chala",
        "chalana",
        "handle",
    )

    CAPABILITY_TERMS = (
        "kya tum",
        "can you",
        "kar sakti",
        "possible hai",
        "possible",
        "capability",
        "kar sakte",
    )

    CLARIFICATION_TERMS = (
        "nahi me",
        "nahi main",
        "nahi,",
        "mera matlab",
        "matlab ye",
        "i mean",
        "not script",
        "script nahi",
        "guide nahi",
        "steps nahi",
        "khud",
    )

    DIRECT_ACTION_TERMS = (
        "kholo",
        "open karo",
        "open kar",
        "band karo",
        "close karo",
        "launch karo",
        "start karo",
        "click karo",
        "type karo",
        "search karo",
        "download karo",
        "play karo",
        "run karo",
    )

    WHOLE_COMPUTER_TERMS = (
        "pura computer",
        "poora computer",
        "pure computer",
        "poore computer",
        "entire computer",
        "whole computer",
        "full computer",
        "pura pc",
        "poora pc",
        "pure pc",
        "poore pc",
        "entire pc",
        "whole pc",
        "full pc",
    )

    def classify(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> IntentDecision:
        """
        Classify a message using the current message plus
        recent structured conversation history.
        """

        normalized = self._normalize(message)

        history_text = self._history_text(
            conversation_history
        )

        # ---------------------------------------------------------
        # 1. Explicit correction / clarification
        # ---------------------------------------------------------
        if self._contains_any(
            normalized,
            self.CLARIFICATION_TERMS,
        ):
            if self._is_computer_context(
                normalized,
                history_text,
            ):
                return IntentDecision(
                    intent="direct_pc_control",
                    handled=True,
                    response=self._direct_pc_control_response(),
                )

        # ---------------------------------------------------------
        # 2. Whole computer follow-up
        # ---------------------------------------------------------
        if self._contains_any(
            normalized,
            self.WHOLE_COMPUTER_TERMS,
        ):
            if self._is_computer_context(
                normalized,
                history_text,
            ):
                return IntentDecision(
                    intent="whole_computer_control",
                    handled=True,
                    response=self._whole_computer_response(),
                )

            # Even without history, "pura computer" strongly
            # indicates the user's intended target.
            return IntentDecision(
                intent="whole_computer_control",
                handled=True,
                response=self._whole_computer_response(),
            )

        # ---------------------------------------------------------
        # 3. Capability question about automation/control
        # ---------------------------------------------------------
        has_automation = self._contains_any(
            normalized,
            self.AUTOMATION_TERMS,
        )

        has_computer = self._contains_any(
            normalized,
            self.COMPUTER_TERMS,
        )

        has_control = self._contains_any(
            normalized,
            self.CONTROL_TERMS,
        )

        is_capability_question = (
            self._contains_any(
                normalized,
                self.CAPABILITY_TERMS,
            )
            or normalized.endswith("?")
        )

        if (
            has_automation
            and is_capability_question
        ):
            return IntentDecision(
                intent="computer_control_capability",
                handled=True,
                response=self._capability_response(),
            )

        if (
            has_computer
            and has_control
            and is_capability_question
        ):
            return IntentDecision(
                intent="computer_control_capability",
                handled=True,
                response=self._capability_response(),
            )

        # ---------------------------------------------------------
        # 4. Direct computer action
        # ---------------------------------------------------------
        if self._contains_any(
            normalized,
            self.DIRECT_ACTION_TERMS,
        ):
            if has_computer or self._is_computer_context(
                normalized,
                history_text,
            ):
                return IntentDecision(
                    intent="computer_action",
                    handled=True,
                    response=self._agent_unavailable_response(
                        action=message.strip(),
                    ),
                )

        # ---------------------------------------------------------
        # 5. "PC automate/control" without question format
        # ---------------------------------------------------------
        if (
            has_automation
            and has_computer
        ):
            return IntentDecision(
                intent="computer_control_capability",
                handled=True,
                response=self._capability_response(),
            )

        if (
            has_control
            and has_computer
        ):
            return IntentDecision(
                intent="computer_control_capability",
                handled=True,
                response=self._capability_response(),
            )

        # ---------------------------------------------------------
        # 6. No special routing
        # ---------------------------------------------------------
        return IntentDecision(
            intent="general_conversation",
            handled=False,
        )

    @staticmethod
    def _normalize(
        message: str,
    ) -> str:
        return " ".join(
            message.lower().strip().split()
        )

    @staticmethod
    def _history_text(
        conversation_history: list[dict[str, str]]
        | None,
    ) -> str:
        if not conversation_history:
            return ""

        parts: list[str] = []

        for item in conversation_history:
            content = item.get("content")

            if not isinstance(content, str):
                continue

            content = content.strip()

            if content:
                parts.append(content.lower())

        return " ".join(parts)

    @classmethod
    def _contains_any(
        cls,
        text: str,
        terms: tuple[str, ...],
    ) -> bool:
        return any(
            term in text
            for term in terms
        )

    @classmethod
    def _is_computer_context(
        cls,
        current_message: str,
        history_text: str,
    ) -> bool:
        combined = (
            f"{current_message} "
            f"{history_text}"
        )

        return (
            cls._contains_any(
                combined,
                cls.COMPUTER_TERMS,
            )
            or cls._contains_any(
                combined,
                cls.AUTOMATION_TERMS,
            )
            or cls._contains_any(
                combined,
                cls.CONTROL_TERMS,
            )
        )

    @staticmethod
    def _capability_response() -> str:
        return (
            "Haan. Zoya ko aapke Windows PC ko directly "
            "control aur use karne ke liye ek secure local "
            "Windows agent se connect kiya ja sakta hai. "
            "Abhi woh agent connected nahi hai, isliye "
            "main is waqt aapke PC par actual action "
            "execute nahi kar sakti."
        )

    @staticmethod
    def _whole_computer_response() -> str:
        return (
            "Samajh gayi. Aap chahte hain ki Zoya aapke "
            "poore Windows PC ko control aur use kare — "
            "jaise apps open karna, browser use karna, "
            "files handle karna aur computer par actions "
            "perform karna. Abhi local Windows agent "
            "connected nahi hai, isliye execution abhi "
            "possible nahi hai."
        )

    @staticmethod
    def _direct_pc_control_response() -> str:
        return (
            "Samajh gayi. Aap scripts ya automation guide "
            "nahi chahte; aap chahte hain ki Zoya khud "
            "aapke PC par actions perform kare. Iske liye "
            "Zoya ke saath secure local Windows agent "
            "connect karna hoga. Abhi agent connected nahi "
            "hai, isliye main actual PC action execute "
            "nahi kar sakti."
        )

    @staticmethod
    def _agent_unavailable_response(
        action: str,
    ) -> str:
        return (
            f"Samajh gayi — aap chahte hain ki Zoya "
            f"computer par ye action kare: "
            f'"{action}". Abhi local Windows agent '
            f"connected nahi hai, isliye main ise "
            f"actual PC par execute nahi kar sakti."
        )