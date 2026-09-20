from dataclasses import dataclass


@dataclass(frozen=True)
class ResponsePlan:
    """
    Describes how Zoya should approach the current request.
    """

    response_length: str
    response_style: str
    needs_structure: bool
    needs_conclusion: bool
    needs_current_information: bool
    needs_step_by_step: bool


class ZoyaBrain:
    """
    Lightweight orchestration layer for Zoya.

    This layer does NOT generate the answer.

    Its job is to decide how the AI should answer the
    current request.

    General conversation remains model-driven. These
    heuristics only provide useful response guidance.
    """

    SHORT_PATTERNS = (
        "what is",
        "who is",
        "when is",
        "where is",
        "why",
        "how much",
        "how many",
        "kya hai",
        "kaun hai",
        "kab hai",
        "kahan hai",
        "kitna",
        "kitne",
    )

    DETAILED_PATTERNS = (
        "detail me",
        "details me",
        "detailed",
        "deeply",
        "deep dive",
        "explain properly",
        "properly explain",
        "step by step",
        "step-by-step",
        "beginner se",
        "advanced tak",
        "complete",
        "completely",
        "everything",
        "full explain",
        "pura explain",
        "detail explain",
    )

    COMPARISON_PATTERNS = (
        "compare",
        "comparison",
        "difference",
        "vs",
        "versus",
        "better than",
        "difference between",
        "compare karo",
        "comparison karo",
        "farak",
    )

    ROADMAP_PATTERNS = (
        "roadmap",
        "plan",
        "strategy",
        "schedule",
        "learning path",
        "kaise seekhu",
        "kaise sikhu",
        "kahan se start",
        "where should i start",
    )

    CURRENT_INFORMATION_PATTERNS = (
        "latest",
        "current",
        "today",
        "today's",
        "recent",
        "recently",
        "abhi",
        "currently",
        "2026",
        "this week",
        "this month",
        "latest news",
        "latest information",
        "recent update",
    )

    STEP_PATTERNS = (
        "how to",
        "kaise",
        "steps",
        "step by step",
        "setup",
        "install",
        "configure",
        "implement",
        "build",
        "create",
        "banau",
        "banao",
        "karna hai",
    )

    def plan(
        self,
        message: str,
        conversation_history: list[dict[str, str]]
        | None = None,
    ) -> ResponsePlan:
        """
        Create a response plan from the current request.

        The model still has final control over the natural
        answer. This plan acts as guidance rather than a
        rigid response template.
        """

        normalized = self._normalize(message)

        is_detailed = self._contains_any(
            normalized,
            self.DETAILED_PATTERNS,
        )

        is_comparison = self._contains_any(
            normalized,
            self.COMPARISON_PATTERNS,
        )

        is_roadmap = self._contains_any(
            normalized,
            self.ROADMAP_PATTERNS,
        )

        needs_current_information = self._contains_any(
            normalized,
            self.CURRENT_INFORMATION_PATTERNS,
        )

        needs_step_by_step = self._contains_any(
            normalized,
            self.STEP_PATTERNS,
        )

        word_count = len(
            normalized.split()
        )

        if is_detailed or is_roadmap:
            response_length = "detailed"

        elif is_comparison:
            response_length = "medium"

        elif (
            word_count <= 8
            and self._contains_any(
                normalized,
                self.SHORT_PATTERNS,
            )
        ):
            response_length = "short"

        elif word_count <= 12:
            response_length = "short"

        else:
            response_length = "medium"

        if is_comparison:
            response_style = "comparison"

        elif is_roadmap:
            response_style = "actionable_plan"

        elif needs_step_by_step:
            response_style = "step_by_step"

        elif needs_current_information:
            response_style = "research_or_current_information"

        elif is_detailed:
            response_style = "deep_explanation"

        else:
            response_style = "direct_explanation"

        needs_structure = (
            response_length == "detailed"
            or response_style in {
                "comparison",
                "actionable_plan",
                "step_by_step",
                "research_or_current_information",
            }
        )

        needs_conclusion = (
            response_length == "detailed"
            or response_style in {
                "comparison",
                "actionable_plan",
                "research_or_current_information",
            }
        )

        return ResponsePlan(
            response_length=response_length,
            response_style=response_style,
            needs_structure=needs_structure,
            needs_conclusion=needs_conclusion,
            needs_current_information=(
                needs_current_information
            ),
            needs_step_by_step=needs_step_by_step,
        )

    @staticmethod
    def _normalize(
        message: str,
    ) -> str:
        return " ".join(
            message.lower().strip().split()
        )

    @staticmethod
    def _contains_any(
        text: str,
        patterns: tuple[str, ...],
    ) -> bool:
        return any(
            pattern in text
            for pattern in patterns
        )

    @staticmethod
    def build_instruction(
        plan: ResponsePlan,
    ) -> str:
        """
        Convert a response plan into concise guidance for
        the language model.
        """

        instructions = [
            "Response planning:",
            (
                f"- Preferred length: "
                f"{plan.response_length}"
            ),
            (
                f"- Preferred style: "
                f"{plan.response_style}"
            ),
        ]

        if plan.needs_structure:
            instructions.append(
                "- Use clear structure when it improves readability."
            )
        else:
            instructions.append(
                "- Keep the response naturally conversational; "
                "do not force headings or sections."
            )

        if plan.needs_step_by_step:
            instructions.append(
                "- Give actionable steps when the user is asking how to do something."
            )

        if plan.needs_conclusion:
            instructions.append(
                "- End with a concise takeaway when the topic is complex enough to benefit from one."
            )
        else:
            instructions.append(
                "- Do not add an artificial 'Conclusion' section to a simple answer."
            )

        if plan.needs_current_information:
            instructions.append(
                "- The request may require current information. "
                "Do not invent current facts. Use an available research/web tool "
                "when one is connected; otherwise clearly state the limitation."
            )

        instructions.extend(
            [
                "- Do not pad the answer just to make it longer.",
                "- Do not make every answer a tutorial.",
                "- Do not ask unnecessary follow-up questions.",
                "- Match the depth to what the user actually asked.",
            ]
        )

        return "\n".join(instructions)