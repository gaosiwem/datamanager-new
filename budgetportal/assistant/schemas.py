"""Strict, database-independent schemas for assistant financial queries."""

import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Optional

from django.core.exceptions import ValidationError


FINANCIAL_YEAR_PATTERN = re.compile(r"^(?P<start>\d{4})-(?P<end>\d{2})$")
FINANCIAL_YEAR_START_PATTERN = re.compile(r"^(?P<start>\d{4})$")


def _normalise_financial_year(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    match = FINANCIAL_YEAR_START_PATTERN.fullmatch(value.strip())
    if not match:
        return value
    start_year = int(match.group("start"))
    return "{}-{:02d}".format(start_year, (start_year + 1) % 100)


class Intent(str, Enum):
    AMOUNT_LOOKUP = "amount_lookup"
    VARIANCE_ANALYSIS = "variance_analysis"
    COMPARISON = "comparison"
    RANKING = "ranking"
    TREND_ANALYSIS = "trend_analysis"
    PERCENTAGE_CHANGE = "percentage_change"


class EntityType(str, Enum):
    DEPARTMENT = "department"
    PROVINCE = "province"
    PROGRAMME = "programme"
    SUBPROGRAMME = "subprogramme"
    FUNCTION_GROUP = "function_group"
    NATIONAL = "national"
    PROVINCIAL = "provincial"
    CONSOLIDATED = "consolidated"


class BudgetPhase(str, Enum):
    MAIN_APPROPRIATION = "Main appropriation"
    ADJUSTED_APPROPRIATION = "Adjusted appropriation"
    TOTAL_ADJUSTMENTS = "Total adjustments"
    BASELINE = "Baseline"
    REVISED_BASELINE = "Revised baseline"
    AUDITED_OUTCOME = "Audited outcome"
    AUDIT_OUTCOME = "Audit Outcome"
    FINAL_APPROPRIATION = "Final Appropriation"
    PRELIMINARY_OUTCOME = "Preliminary outcome"
    MEDIUM_TERM_ESTIMATES = "Medium Term Estimates"


class GroupBy(str, Enum):
    DEPARTMENT = "department"
    PROVINCE = "province"
    PROGRAMME = "programme"
    SUBPROGRAMME = "subprogramme"
    FUNCTION_GROUP = "function_group"
    ECONOMIC_CLASSIFICATION_2 = "economic_classification_2"
    ECONOMIC_CLASSIFICATION_3 = "economic_classification_3"
    FINANCIAL_YEAR = "financial_year"


class VarianceDirection(str, Enum):
    INCREASE = "increase"
    DECREASE = "decrease"
    ABSOLUTE = "absolute"
    UNDERSPENDING = "underspending"
    OVERSPENDING = "overspending"


class DirectChargeScope(str, Enum):
    ALL = "all"
    VOTED = "voted"
    DIRECT_CHARGES = "direct_charges"


class Metric(str, Enum):
    BUDGET = "budget"
    ADJUSTED_BUDGET = "adjusted_budget"
    ACTUAL = "actual"
    VALUE = "value"


class PortalDataset(str, Enum):
    """Published non-budget datasets supported by the portal query layer."""

    PUBLIC_ENTITY = "public_entity"
    INFRASTRUCTURE = "infrastructure"
    PERFORMANCE = "performance"


class PortalIntent(str, Enum):
    LOOKUP = "lookup"
    AMOUNT_LOOKUP = "amount_lookup"
    RANKING = "ranking"
    LIST = "list"


@dataclass(frozen=True)
class PortalDataQuery:
    """Validated query plan for a non-budget Vulekamali dataset.

    The parser supplies only user intent and filters.  Dataset adapters own
    their ORM queries and therefore no model-generated text can execute SQL or
    select an unpublished field.
    """

    dataset: PortalDataset
    intent: PortalIntent
    entity_name: Optional[str] = None
    financial_year: Optional[str] = None
    budget_phase: Optional[str] = None
    limit: Optional[int] = None
    descending: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.dataset, PortalDataset):
            raise ValidationError({"dataset": "Must be a supported portal dataset."})
        if not isinstance(self.intent, PortalIntent):
            raise ValidationError({"intent": "Must be a supported portal intent."})
        _optional_text(self.entity_name, "entity_name")
        _optional_text(self.budget_phase, "budget_phase")
        if self.financial_year is not None:
            _validate_financial_year(self.financial_year, "financial_year")
        if self.limit is not None and (
            isinstance(self.limit, bool)
            or not isinstance(self.limit, int)
            or not 1 <= self.limit <= 100
        ):
            raise ValidationError({"limit": "Must be an integer between 1 and 100."})
        if not isinstance(self.descending, bool):
            raise ValidationError({"descending": "Must be a boolean."})
        if self.intent == PortalIntent.RANKING and self.limit is None:
            raise ValidationError({"limit": "Ranking queries require a limit."})

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PortalDataQuery":
        if not isinstance(value, Mapping):
            raise ValidationError({"query": "Must be an object."})
        unexpected_fields = set(value) - set(cls.__dataclass_fields__)
        if unexpected_fields:
            raise ValidationError({"query": "Unexpected fields: {}.".format(
                ", ".join(sorted(unexpected_fields))
            )})
        parsed = dict(value)
        for field_name, enum_type in (("dataset", PortalDataset), ("intent", PortalIntent)):
            if field_name not in parsed:
                raise ValidationError({field_name: "This field is required."})
            try:
                parsed[field_name] = enum_type(parsed[field_name])
            except (TypeError, ValueError):
                raise ValidationError({field_name: "Contains an unsupported value."})
        for field_name in ("entity_name", "budget_phase"):
            if field_name in parsed:
                parsed[field_name] = _optional_text(parsed[field_name], field_name)
        if parsed.get("financial_year") is not None:
            parsed["financial_year"] = _normalise_financial_year(parsed["financial_year"])
        return cls(**parsed)

    def to_dict(self) -> Dict[str, Any]:
        output = asdict(self)
        for field_name, value in output.items():
            if isinstance(value, Enum):
                output[field_name] = value.value
        return output


def _validate_financial_year(value: str, field_name: str) -> str:
    match = FINANCIAL_YEAR_PATTERN.fullmatch(value)
    if not match:
        raise ValidationError(
            {field_name: "Use the financial-year format YYYY-YY, for example 2024-25."}
        )

    start_year = int(match.group("start"))
    end_year = int(match.group("end"))
    if end_year != (start_year + 1) % 100:
        raise ValidationError(
            {
                field_name: "The financial year must end in the year immediately after it starts."
            }
        )
    return value


def _optional_text(value: Optional[str], field_name: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError({field_name: "Must be a string."})
    value = value.strip()
    if not value:
        raise ValidationError({field_name: "Must not be blank."})
    return value


@dataclass(frozen=True)
class BudgetQuery:
    """A validated, structured financial query.

    ``from_dict`` is the public boundary for untrusted input. This schema only
    validates structure; later components will resolve entities and execute
    whitelisted ORM queries.
    """

    intent: Intent
    entity_type: Optional[EntityType] = None
    department: Optional[str] = None
    comparison_department: Optional[str] = None
    province: Optional[str] = None
    comparison_province: Optional[str] = None
    programme: Optional[str] = None
    subprogramme: Optional[str] = None
    financial_year: Optional[str] = None
    comparison_year: Optional[str] = None
    ambiguous_time_reference: Optional[str] = None
    budget_phase: Optional[BudgetPhase] = None
    comparison_phase: Optional[BudgetPhase] = None
    group_by: Optional[GroupBy] = None
    limit: Optional[int] = None
    descending: bool = True
    variance_direction: Optional[VarianceDirection] = None
    direct_charge_scope: Optional[DirectChargeScope] = None
    metric: Optional[Metric] = None

    def __post_init__(self) -> None:
        if not isinstance(self.intent, Intent):
            raise ValidationError({"intent": "Must be a supported intent."})
        for field_name, enum_type in (
            ("entity_type", EntityType),
            ("budget_phase", BudgetPhase),
            ("comparison_phase", BudgetPhase),
            ("group_by", GroupBy),
            ("variance_direction", VarianceDirection),
            ("direct_charge_scope", DirectChargeScope),
            ("metric", Metric),
        ):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, enum_type):
                raise ValidationError({field_name: "Contains an unsupported value."})

        for field_name in (
            "department",
            "comparison_department",
            "province",
            "comparison_province",
            "programme",
            "subprogramme",
            "ambiguous_time_reference",
        ):
            _optional_text(getattr(self, field_name), field_name)

        if self.financial_year is not None:
            _validate_financial_year(self.financial_year, "financial_year")
        if self.comparison_year is not None:
            _validate_financial_year(self.comparison_year, "comparison_year")
        if isinstance(self.descending, bool) is False:
            raise ValidationError({"descending": "Must be a boolean."})
        if self.limit is not None and (
            isinstance(self.limit, bool)
            or not isinstance(self.limit, int)
            or not 1 <= self.limit <= 100
        ):
            raise ValidationError({"limit": "Must be an integer between 1 and 100."})

        if self.intent == Intent.RANKING and self.group_by is None:
            raise ValidationError({"group_by": "Ranking queries require group_by."})

        if (
            self.intent
            in (
                Intent.VARIANCE_ANALYSIS,
                Intent.COMPARISON,
                Intent.PERCENTAGE_CHANGE,
            )
            and not self._has_comparison_target()
        ):
            raise ValidationError(
                {
                    "comparison": (
                        "A comparison query requires a comparison department, province, "
                        "year, or budget phase."
                    )
                }
            )

    def _has_comparison_target(self) -> bool:
        return any(
            (
                self.comparison_department,
                self.comparison_province,
                self.comparison_year,
                self.comparison_phase,
            )
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BudgetQuery":
        if not isinstance(value, Mapping):
            raise ValidationError({"query": "Must be an object."})

        allowed_fields = set(cls.__dataclass_fields__)
        unexpected_fields = set(value) - allowed_fields
        if unexpected_fields:
            raise ValidationError(
                {
                    "query": "Unexpected fields: {}.".format(
                        ", ".join(sorted(unexpected_fields))
                    )
                }
            )

        if "intent" not in value:
            raise ValidationError({"intent": "This field is required."})

        parsed = dict(value)
        for field_name, enum_type in (
            ("intent", Intent),
            ("entity_type", EntityType),
            ("budget_phase", BudgetPhase),
            ("comparison_phase", BudgetPhase),
            ("group_by", GroupBy),
            ("variance_direction", VarianceDirection),
            ("direct_charge_scope", DirectChargeScope),
            ("metric", Metric),
        ):
            if field_name in parsed and parsed[field_name] is not None:
                try:
                    parsed[field_name] = enum_type(parsed[field_name])
                except (TypeError, ValueError):
                    raise ValidationError(
                        {field_name: "Contains an unsupported value."}
                    )

        for field_name in (
            "department",
            "comparison_department",
            "province",
            "comparison_province",
            "programme",
            "subprogramme",
            "ambiguous_time_reference",
        ):
            if field_name in parsed:
                parsed[field_name] = _optional_text(parsed[field_name], field_name)

        for field_name in ("financial_year", "comparison_year"):
            if field_name in parsed and parsed[field_name] is not None:
                parsed[field_name] = _normalise_financial_year(parsed[field_name])

        return cls(**parsed)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-safe representation for a downstream query engine."""
        output = asdict(self)
        for field_name, value in output.items():
            if isinstance(value, Enum):
                output[field_name] = value.value
        return output
