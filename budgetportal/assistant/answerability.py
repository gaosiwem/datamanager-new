"""Deterministic checks that verified budget data is sufficient to answer."""

from dataclasses import dataclass
from typing import Literal

from budgetportal.assistant.budget_query_engine import (
    NEEDS_BUDGET_PHASE,
    NO_MATCHING_SOURCE_RECORDS,
    OK,
    UNSUPPORTED_VARIANCE_DEFINITION,
    BudgetQueryResult,
)
from budgetportal.assistant.schemas import BudgetQuery, Intent


AnswerabilityStatus = Literal["answerable", "insufficient_data", "unsupported"]


@dataclass(frozen=True)
class AnswerabilityDecision:
    status: AnswerabilityStatus
    reason: str
    # Public API code can expose this deterministic status without revealing
    # data-source internals.  It deliberately differs from scope rejection.
    response_status: str


class AnswerabilityChecker:
    """Determine answerability without an LLM or inferred financial facts."""

    def __init__(self, minimum_trend_observations: int = 2):
        if minimum_trend_observations < 1:
            raise ValueError("minimum_trend_observations must be at least one.")
        self.minimum_trend_observations = minimum_trend_observations

    def assess(
        self, query: BudgetQuery, result: BudgetQueryResult
    ) -> AnswerabilityDecision:
        if result.intent != query.intent.value:
            return self._unsupported(
                "The verified result does not match the requested intent."
            )
        if result.status in (NEEDS_BUDGET_PHASE, UNSUPPORTED_VARIANCE_DEFINITION):
            return self._unsupported(
                "The requested calculation is not supported as specified."
            )
        if result.status != OK:
            return self._insufficient(
                "No matching Vulekamali source records are available."
            )

        source_counts = [
            source.get("record_count", 0) for source in result.source_metadata
        ]
        if query.intent == Intent.AMOUNT_LOOKUP:
            return self._require(
                source_counts, 1, "No matching Vulekamali source records are available."
            )
        if query.intent in (
            Intent.VARIANCE_ANALYSIS,
            Intent.PERCENTAGE_CHANGE,
            Intent.COMPARISON,
        ):
            return self._require(
                source_counts,
                2,
                "Both values required for this comparison are not available.",
            )
        if query.intent == Intent.RANKING:
            requested = query.limit or 10
            if len(result.values) < requested:
                return self._insufficient(
                    "There are not enough valid records for the requested ranking."
                )
            return self._answerable()
        if query.intent == Intent.TREND_ANALYSIS:
            observations = sum(
                1 for item in result.values if item.get("amount") is not None
            )
            if observations < self.minimum_trend_observations:
                return self._insufficient(
                    "There are not enough observations for the requested trend."
                )
            return self._answerable()
        return self._unsupported("The requested intent is not supported.")

    def _require(self, counts, required, reason):
        if len(counts) < required or any(count < 1 for count in counts[:required]):
            return self._insufficient(reason)
        return self._answerable()

    @staticmethod
    def _answerable():
        return AnswerabilityDecision(
            "answerable", "Verified source data is sufficient.", "answerable"
        )

    @staticmethod
    def _insufficient(reason):
        return AnswerabilityDecision("insufficient_data", reason, "data_not_found")

    @staticmethod
    def _unsupported(reason):
        return AnswerabilityDecision("unsupported", reason, "unsupported")
