"""Foundry-backed interpretation for non-budget portal datasets."""

import json

from django.core.exceptions import ValidationError

from .foundry_client import FoundryClient
from .question_parser import QuestionParsingError
from .schemas import PortalDataQuery, PortalDataset, PortalIntent


PORTAL_DATA_QUERY_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "vulekamali_portal_data_query",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "dataset", "intent", "entity_name", "financial_year",
                "budget_phase", "limit", "descending",
            ],
            "properties": {
                "dataset": {"type": "string", "enum": [item.value for item in PortalDataset]},
                "intent": {"type": "string", "enum": [item.value for item in PortalIntent]},
                "entity_name": {"type": ["string", "null"]},
                "financial_year": {"type": ["string", "null"]},
                "budget_phase": {"type": ["string", "null"]},
                "limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 100},
                "descending": {"type": "boolean"},
            },
        },
    },
}


PORTAL_DATA_PARSER_PROMPT = """Interpret a Vulekamali question into a PortalDataQuery only.
Never answer the question, retrieve amounts, calculate values, generate SQL, or invent entities.
The dataset is supplied by the application and must not be changed.

Use lookup for facts about one named record, amount_lookup for a named record's amount,
list for a set of published records, and ranking for highest, lowest, largest, smallest,
most expensive, least expensive, top, or bottom requests. Preserve a named entity exactly
as the user wrote it.
Use a YYYY-YY financial year. Convert an explicit four-digit financial-year start such as
2026 to 2026-27. For a ranking question, set a limit (one for singular wording).
When the user explicitly says allocated, allocation, or appropriated, use the exact phase
Main appropriation. Do not infer a phase from generic budget wording.
Return only JSON conforming to the supplied schema."""


class PortalDataQuestionParser:
    """Convert a portal-data request into a small, validated query plan."""

    def __init__(self, client=None):
        self.client = client or FoundryClient()

    def parse(self, question, dataset):
        if not isinstance(question, str) or not question.strip():
            raise QuestionParsingError("A question is required.")
        try:
            selected_dataset = PortalDataset(dataset)
        except (TypeError, ValueError):
            raise QuestionParsingError("The portal dataset is not supported.")
        response = self.client.complete_chat(
            messages=[
                {"role": "system", "content": PORTAL_DATA_PARSER_PROMPT},
                {"role": "user", "content": "Dataset: {}\nQuestion: {}".format(
                    selected_dataset.value, question.strip()
                )},
            ],
            purpose="intent_parsing",
            max_tokens=220,
            temperature=0,
            response_format=PORTAL_DATA_QUERY_JSON_SCHEMA,
        )
        try:
            content = response["choices"][0]["message"]["content"]
            query = PortalDataQuery.from_dict(json.loads(content))
        except (IndexError, KeyError, TypeError, ValueError, ValidationError):
            raise QuestionParsingError("The question could not be interpreted safely.")
        if query.dataset != selected_dataset:
            raise QuestionParsingError("The question could not be interpreted safely.")
        return query
