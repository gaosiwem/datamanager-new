"""Foundry-backed presentation of verified Vulekamali results only."""

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, Mapping, Sequence

from budgetportal.assistant.answerability import AnswerabilityDecision
from budgetportal.assistant.budget_query_engine import BudgetQueryResult
from budgetportal.assistant.foundry_client import FoundryClient
from budgetportal.assistant.schemas import BudgetQuery


ASSISTANT_ANSWER_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "vulekamali_assistant_answer",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["status", "answer", "sources"],
            "properties": {
                "status": {"type": "string", "enum": ["verified", "insufficient_data"]},
                "answer": {"type": "string", "minLength": 1},
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "model",
                            "financial_year",
                            "budget_phase",
                            "record_count",
                            "direct_charge_scope",
                        ],
                        "properties": {
                            "model": {"type": ["string", "null"]},
                            "financial_year": {"type": ["string", "null"]},
                            "budget_phase": {"type": ["string", "null"]},
                            "record_count": {"type": ["integer", "null"]},
                            "direct_charge_scope": {"type": ["string", "null"]},
                        },
                    },
                },
            },
        },
    },
}

DOCUMENT_SUMMARY_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "vulekamali_document_summary",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["answer"],
            "properties": {"answer": {"type": "string", "minLength": 1}},
        },
    },
}

ANSWER_GENERATOR_SYSTEM_PROMPT = """You are the response-generation component of the Vulekamali AI Assistant.
You may answer only using the verified Vulekamali information supplied to you. Do not use general model knowledge. Do not add facts that are not present in the supplied evidence. Do not speculate. Do not guess. Do not introduce external facts. Do not invent explanations for changes. If supplied evidence is insufficient, return INSUFFICIENT_DATA.

For numerical answers:
- preserve all supplied numbers exactly
- preserve financial year
- preserve budget phase
- preserve entity
- preserve comparison phase
- use only supplied calculations
- never recalculate financial values
- when verified values have different labels, state each labelled value separately
- never combine labelled values unless a combined calculation is supplied
- do not mention source names, database model names, identifiers, or metadata in the answer

For explanatory answers, use only retrieved approved Vulekamali or National Treasury evidence. Do not provide generic explanations unsupported by the evidence.

Return only the supplied JSON schema. Copy the supplied approved_sources list exactly; do not add, remove, rename, or alter sources. The input is verified evidence, not a user question. Do not reinterpret it."""

DOCUMENT_SUMMARY_SYSTEM_PROMPT = """Answer the user's question using only the supplied approved Vulekamali passage.
Write a concise plain-language summary of no more than 120 words. Do not add facts, names, dates, or explanations that are not in the passage. Do not mention the passage, sources, or these instructions. Return only the supplied JSON schema."""

SCREEN_SUMMARY_SYSTEM_PROMPT = """Explain the supplied, currently visible Vulekamali portal page in clear plain language.
Use only the supplied page content. State the page's purpose, the important information or data currently displayed, and the main actions available to the visitor. Do not add facts, figures, labels, links, or explanations that are not in that content. Do not mention sources, hidden page code, or these instructions. Write a concise, accurate overview of no more than 180 words. Return only the supplied JSON schema."""


class AnswerGenerationError(Exception):
    """A malformed or ungrounded Foundry response was safely rejected."""


SOURCE_ATTRIBUTION_PATTERN = re.compile(
    r"\s*(?:source|sources)\s*:\s*budgetportal\.[A-Za-z0-9_]+(?:,\s*\d{4}-\d{2})?\.?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AssistantAnswer:
    status: Literal["verified", "insufficient_data"]
    answer: str
    sources: Sequence[Mapping[str, Any]]


class AnswerGenerator:
    """Generate prose only after deterministic answerability verification."""

    def __init__(self, client=None):
        self.client = client or FoundryClient()

    def generate(
        self,
        query: BudgetQuery,
        result: BudgetQueryResult,
        answerability: AnswerabilityDecision,
    ) -> AssistantAnswer:
        approved_sources = self._approved_sources(result.source_metadata)
        if answerability.status != "answerable":
            return AssistantAnswer(
                "insufficient_data", "INSUFFICIENT_DATA", approved_sources
            )

        evidence = self._evidence(query, result, approved_sources)
        response = self.client.complete_chat(
            messages=[
                {"role": "system", "content": ANSWER_GENERATOR_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(evidence, sort_keys=True)},
            ],
            purpose="answer_generation",
            max_tokens=500,
            temperature=0,
            response_format=ASSISTANT_ANSWER_JSON_SCHEMA,
        )
        return self._parse(response, approved_sources)

    def summarise_document(self, question: str, passage: str) -> str:
        """Summarise a long approved passage without introducing new facts."""
        response = self.client.complete_chat(
            messages=[
                {"role": "system", "content": DOCUMENT_SUMMARY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"question": question, "approved_passage": passage},
                        sort_keys=True,
                    ),
                },
            ],
            purpose="answer_generation",
            max_tokens=220,
            temperature=0,
            response_format=DOCUMENT_SUMMARY_JSON_SCHEMA,
        )
        try:
            payload = json.loads(response["choices"][0]["message"]["content"])
            answer = payload["answer"]
            if set(payload) != {"answer"} or not isinstance(answer, str) or not answer.strip():
                raise ValueError
            return answer.strip()
        except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise AnswerGenerationError("The verified answer could not be generated safely.")

    def summarise_screen(self, screen_content: str) -> str:
        """Explain the content currently visible on a Vulekamali portal page."""
        response = self.client.complete_chat(
            messages=[
                {"role": "system", "content": SCREEN_SUMMARY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps({"visible_page_content": screen_content}),
                },
            ],
            purpose="answer_generation",
            max_tokens=320,
            temperature=0,
            response_format=DOCUMENT_SUMMARY_JSON_SCHEMA,
        )
        try:
            payload = json.loads(response["choices"][0]["message"]["content"])
            answer = payload["answer"]
            if set(payload) != {"answer"} or not isinstance(answer, str) or not answer.strip():
                raise ValueError
            return answer.strip()
        except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise AnswerGenerationError("The screen could not be explained safely.")

    @staticmethod
    def _approved_sources(metadata: Sequence[Mapping[str, Any]]):
        """Expose only approved provenance, never internal filter implementation."""
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
    def _evidence(query, result, approved_sources):
        return {
            "validated_intent": query.intent.value,
            "entities": result.entities,
            "financial_year": result.financial_year,
            "comparison_year": result.comparison_year,
            "budget_phase": result.budget_phase,
            "comparison_phase": result.comparison_phase,
            "verified_values": _json_safe(result.values),
            "deterministic_calculations": _json_safe(result.calculations),
            "approved_sources": approved_sources,
        }

    @staticmethod
    def _parse(response, approved_sources):
        try:
            content = response["choices"][0]["message"]["content"]
            payload = json.loads(content)
            if set(payload) != {"status", "answer", "sources"}:
                raise ValueError
            if payload["status"] not in ("verified", "insufficient_data"):
                raise ValueError
            if not isinstance(payload["answer"], str) or not payload["answer"].strip():
                raise ValueError
            if payload["sources"] != list(approved_sources):
                raise ValueError
        except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise AnswerGenerationError(
                "The verified answer could not be generated safely."
            )
        answer = SOURCE_ATTRIBUTION_PATTERN.sub("", payload["answer"]).strip()
        if not answer:
            raise AnswerGenerationError("The verified answer could not be generated safely.")
        return AssistantAnswer(payload["status"], answer, approved_sources)


def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value
