"""Foundry-backed language interpretation for Vulekamali budget questions."""

import json
import re
from dataclasses import replace

from django.core.exceptions import ValidationError

from .foundry_client import FoundryClient
from .schemas import (
    BudgetPhase,
    BudgetQuery,
    DirectChargeScope,
    EntityType,
    GroupBy,
    Intent,
    Metric,
    VarianceDirection,
)


class QuestionParsingError(Exception):
    """An untrusted parser response was malformed or invalid."""


BUDGET_QUERY_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "vulekamali_budget_query",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "intent",
                "entity_type",
                "department",
                "comparison_department",
                "province",
                "comparison_province",
                "programme",
                "subprogramme",
                "financial_year",
                "comparison_year",
                "ambiguous_time_reference",
                "budget_phase",
                "comparison_phase",
                "group_by",
                "limit",
                "descending",
                "variance_direction",
                "direct_charge_scope",
                "metric",
            ],
            "properties": {
                "intent": {"type": "string", "enum": [item.value for item in Intent]},
                "entity_type": {
                    "anyOf": [
                        {"type": "string", "enum": [item.value for item in EntityType]},
                        {"type": "null"},
                    ]
                },
                "department": {"type": ["string", "null"]},
                "comparison_department": {"type": ["string", "null"]},
                "province": {"type": ["string", "null"]},
                "comparison_province": {"type": ["string", "null"]},
                "programme": {"type": ["string", "null"]},
                "subprogramme": {"type": ["string", "null"]},
                "financial_year": {"type": ["string", "null"]},
                "comparison_year": {"type": ["string", "null"]},
                "ambiguous_time_reference": {"type": ["string", "null"]},
                "budget_phase": {
                    "anyOf": [
                        {
                            "type": "string",
                            "enum": [item.value for item in BudgetPhase],
                        },
                        {"type": "null"},
                    ]
                },
                "comparison_phase": {
                    "anyOf": [
                        {
                            "type": "string",
                            "enum": [item.value for item in BudgetPhase],
                        },
                        {"type": "null"},
                    ]
                },
                "group_by": {
                    "anyOf": [
                        {"type": "string", "enum": [item.value for item in GroupBy]},
                        {"type": "null"},
                    ]
                },
                "limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 100},
                "descending": {"type": "boolean"},
                "variance_direction": {
                    "anyOf": [
                        {
                            "type": "string",
                            "enum": [item.value for item in VarianceDirection],
                        },
                        {"type": "null"},
                    ]
                },
                "direct_charge_scope": {
                    "anyOf": [
                        {
                            "type": "string",
                            "enum": [item.value for item in DirectChargeScope],
                        },
                        {"type": "null"},
                    ]
                },
                "metric": {
                    "anyOf": [
                        {"type": "string", "enum": [item.value for item in Metric]},
                        {"type": "null"},
                    ]
                },
            },
        },
    },
}

QUESTION_PARSER_SYSTEM_PROMPT = """You interpret a Vulekamali user question into a structured BudgetQuery only.
You must never retrieve amounts, calculate values, answer the user, generate SQL, execute SQL, invent departments, invent programmes, invent budget figures, or infer unavailable financial facts.

Supported intents are amount_lookup, variance_analysis, comparison, ranking, trend_analysis, and percentage_change.
Examples:
- What was Police allocated in 2023-24? -> amount_lookup
- How much of National Treasury's final appropriation was unused in 2023-24? -> variance_analysis; budget_phase Final Appropriation; comparison_phase Audit Outcome; variance_direction underspending
- Compare Health and Police allocations in 2024-25. -> comparison
- Which five departments had the largest final appropriations in 2023-24? -> ranking; limit 5
- Which programme of National Health has the highest allocation in 2026? -> ranking; department Health; entity_type national; group_by programme; limit 1; budget_phase Main appropriation
- Show Police expenditure over the last five financial years. -> trend_analysis
- By what percentage did the allocation increase from 2023-24 to 2024-25? -> percentage_change

Preserve the user's entity wording exactly for later entity resolution. Treasury, NT, and National Treasury may be references to a department, as may Police, SAPS, and South African Police Service; Home Affairs and DHA may also be references. Do not decide whether they match an entity.
Populate financial_year or comparison_year for an explicit YYYY-YY value or a four-digit financial-year start value. A value such as 2024 means financial year 2024-25; return it as 2024-25. Keep calendar ranges and relative periods in ambiguous_time_reference unless they identify one explicit financial year.
For amount lookups, rankings, comparisons, trends, and percentage changes, the explicit words allocated, allocation, or appropriated mean Main appropriation. Do not apply this rule to other budget-phase wording.
Return only a BudgetQuery JSON object that conforms to the supplied schema."""


ALLOCATION_WORDING = re.compile(r"\b(?:allocated|allocation|appropriated)\b", re.I)
SPENDING_WORDING = re.compile(
    r"\b(?:spend|spent|spending|actual|actuals|expenditure)\b", re.I
)


class BudgetQuestionParser:
    """Use Foundry for language interpretation, then validate locally."""

    def __init__(self, client=None) -> None:
        self.client = client or FoundryClient()

    def parse(self, question: str) -> BudgetQuery:
        if not isinstance(question, str) or not question.strip():
            raise QuestionParsingError("A question is required.")
        response = self.client.complete_chat(
            messages=[
                {"role": "system", "content": QUESTION_PARSER_SYSTEM_PROMPT},
                {"role": "user", "content": question.strip()},
            ],
            purpose="intent_parsing",
            max_tokens=350,
            temperature=0,
            response_format=BUDGET_QUERY_JSON_SCHEMA,
        )
        try:
            content = response["choices"][0]["message"]["content"]
            query = BudgetQuery.from_dict(json.loads(content))
            return self._apply_explicit_phase_rule(question, query)
        except (IndexError, KeyError, TypeError, ValueError, ValidationError):
            raise QuestionParsingError("The question could not be interpreted safely.")

    @staticmethod
    def _apply_explicit_phase_rule(question: str, query: BudgetQuery) -> BudgetQuery:
        """Apply the documented allocation-to-main-appropriation rule.

        This is deliberately narrow and deterministic. It makes the selected
        phase visible in the returned query and answer rather than silently
        substituting a phase for generic budget wording.
        """
        if (
            query.intent == Intent.AMOUNT_LOOKUP
            and query.budget_phase is None
            and ALLOCATION_WORDING.search(question)
        ):
            return replace(query, budget_phase=BudgetPhase.MAIN_APPROPRIATION)
        if (
            query.intent == Intent.AMOUNT_LOOKUP
            and query.budget_phase is None
            and SPENDING_WORDING.search(question)
        ):
            return replace(query, budget_phase=BudgetPhase.AUDITED_OUTCOME)
        return query
