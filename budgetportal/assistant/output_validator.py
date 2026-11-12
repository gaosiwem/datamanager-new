"""Post-generation grounding validation and deterministic answer fallback."""

import logging
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Sequence

from budgetportal.assistant.answer_generator import AssistantAnswer
from budgetportal.assistant.budget_query_engine import BudgetQueryResult
from budgetportal.assistant.schemas import BudgetQuery, VarianceDirection


logger = logging.getLogger(__name__)

CAUSAL_EXPLANATION_PATTERN = re.compile(
    r"\b(because|due to|caused by|as a result of|explains? why|reason for)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class OutputValidationResult:
    answer: AssistantAnswer
    fallback_used: bool
    failure_reason: str = ""


class AnswerOutputValidator:
    """Never send an answer that differs from verified Vulekamali evidence."""

    def __init__(self):
        self.fallback_count = 0

    def validate_or_fallback(
        self, query: BudgetQuery, result: BudgetQueryResult, answer: Any
    ) -> OutputValidationResult:
        failure = self._failure_reason(query, result, answer)
        if failure:
            self.fallback_count += 1
            logger.warning("Vulekamali answer fallback used reason=%s", failure)
            return OutputValidationResult(self._fallback(query, result), True, failure)
        return OutputValidationResult(answer, False)

    def _failure_reason(self, query, result, answer):
        if not isinstance(answer, AssistantAnswer):
            return "malformed_foundry_output"
        if answer.status == "insufficient_data":
            return None
        if answer.status != "verified" or not isinstance(answer.answer, str):
            return "malformed_foundry_output"
        if tuple(answer.sources) != self._approved_sources(result.source_metadata):
            return "missing_or_changed_source"

        text = answer.answer.strip()
        if not text:
            return "malformed_foundry_output"
        if CAUSAL_EXPLANATION_PATTERN.search(text):
            return "invented_explanation"
        if "source" not in text.casefold():
            return "missing_source"
        for entity in self._entities(result):
            if entity.casefold() not in text.casefold():
                return "changed_entity"
        for value in self._required_text_values(result):
            if not self._contains_value(text, value):
                return "changed_verified_value"
        if not self._sentences_are_anchored(text, result):
            return "unrelated_extra_information"
        return ""

    @staticmethod
    def _approved_sources(metadata: Sequence[Mapping[str, Any]]):
        return tuple(
            {
                "model": source.get("model"),
                "financial_year": source.get("financial_year"),
                "budget_phase": source.get("budget_phase"),
                "record_count": source.get("record_count"),
                "direct_charge_scope": source.get("direct_charge_scope"),
            }
            for source in metadata
        )

    @staticmethod
    def _entities(result):
        return tuple(value for value in result.entities.values() if value)

    @staticmethod
    def _required_text_values(result):
        values = [
            result.financial_year,
            result.comparison_year,
            result.budget_phase,
            result.comparison_phase,
        ]
        for entry in result.values:
            if entry.get("amount") is not None:
                values.append(entry["amount"])
        values.extend(
            value
            for value in result.calculations.values()
            if value is not None and not isinstance(value, bool)
        )
        values.extend(
            source.get("model")
            for source in result.source_metadata
            if source.get("model")
        )
        return tuple(value for value in values if value is not None)

    @staticmethod
    def _contains_value(text, value):
        if isinstance(value, Decimal):
            return any(
                re.search(pattern, text, re.IGNORECASE)
                for pattern in _decimal_patterns(value)
            )
        return str(value).casefold() in text.casefold()

    def _sentences_are_anchored(self, text, result):
        anchors = [
            str(value).casefold()
            for value in self._entities(result)
            + tuple(
                value
                for value in (
                    result.financial_year,
                    result.comparison_year,
                    result.budget_phase,
                    result.comparison_phase,
                )
                if value
            )
        ]
        anchors.extend("source" for _ in result.source_metadata)
        required_values = self._required_text_values(result)
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            sentence = sentence.strip()
            if sentence and not (
                any(anchor in sentence.casefold() for anchor in anchors)
                or any(
                    self._contains_value(sentence, value) for value in required_values
                )
            ):
                return False
        return True

    def _fallback(self, query, result):
        parts = []
        entity = next(iter(self._entities(result)), "The requested entity")
        if result.intent == "variance_analysis" and "variance" in result.calculations:
            descriptor = (
                "underspending"
                if query.variance_direction == VarianceDirection.UNDERSPENDING
                else "variance"
            )
            parts.append(
                "{} recorded {} of {} in {}.".format(
                    entity,
                    descriptor,
                    _format_currency(result.calculations["variance"]),
                    result.financial_year,
                )
            )
        else:
            parts.append(
                "Verified Vulekamali result for {} in {}.".format(
                    entity, result.financial_year
                )
            )
        for entry in result.values:
            if entry.get("amount") is not None:
                parts.append(
                    "{}: {}.".format(
                        entry.get("label", entry.get("entity", "Amount")),
                        _format_currency(entry["amount"]),
                    )
                )
        for name, value in result.calculations.items():
            if value is not None and not isinstance(value, bool):
                label = name.replace("_", " ").title()
                if "percentage" in name:
                    parts.append("{}: {}%.".format(label, _format_decimal(value)))
                else:
                    parts.append("{}: {}.".format(label, _format_currency(value)))
        for source in self._approved_sources(result.source_metadata):
            parts.append(
                "Source: {}, {}{}".format(
                    source["model"],
                    source["financial_year"],
                    "." if source["financial_year"] else ".",
                )
            )
        return AssistantAnswer(
            "verified", " ".join(parts), self._approved_sources(result.source_metadata)
        )


def _decimal_patterns(value: Decimal):
    raw = _format_decimal(value)
    comma = _strip_fraction(format(value, ",f"))
    escaped_raw, escaped_comma = re.escape(raw), re.escape(comma)
    return (
        r"\b{}\b".format(escaped_raw),
        r"R\s*{}\b".format(escaped_comma),
        r"\b{}%".format(escaped_raw),
    )


def _format_decimal(value):
    return _strip_fraction(format(Decimal(value), "f"))


def _format_currency(value):
    return "R{}".format(_strip_fraction(format(Decimal(value), ",f")))


def _strip_fraction(value):
    return value.rstrip("0").rstrip(".") if "." in value else value
