"""Deterministic validation and entity resolution for assistant queries.

This module deliberately uses the Vulekamali ORM as its source of truth.  It
does not use an LLM and it does not create its own catalogue of departments or
programmes.  The small alias map exists because the current canonical models do
not have alias fields; aliases resolve *to* canonical ORM records and never to
database identifiers.
"""

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum
import re
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from budgetportal.assistant.financial_year_resolver import (
    FinancialYearResolutionStatus,
    FinancialYearResolver,
    source_financial_year_values,
)
from budgetportal.assistant.schemas import BudgetQuery, EntityType
from budgetportal.models import (
    AENEData,
    BudgetVSActualNationalData,
    BudgetVSActualProvincialData,
    ENEData,
    EPREData,
)
from budgetportal.models.government import (
    Department,
    FinancialYear,
    Government,
    Programme,
    Sphere,
)


class ResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    UNKNOWN_ENTITY = "UNKNOWN_ENTITY"
    AMBIGUOUS_ENTITY = "AMBIGUOUS_ENTITY"


@dataclass(frozen=True)
class EntityResolution:
    status: ResolutionStatus
    entity_type: str
    supplied_value: str
    canonical_name: Optional[str] = None
    entity: Optional[Any] = None
    candidates: Tuple[str, ...] = ()
    # Keep the bounded, ORM-backed candidates internally.  The public API
    # never serialises these model instances; it uses them only for the narrow
    # multi-department amount-lookup path in ``api.py``.
    candidate_entities: Tuple[Any, ...] = ()


@dataclass(frozen=True)
class EntityValidationResult:
    status: ResolutionStatus
    resolved: Mapping[str, EntityResolution] = field(default_factory=dict)
    failed_field: Optional[str] = None


# The project has no alias model or alternative-name fields.  Keep this small,
# reviewable map of documented public abbreviations and always resolve its
# target through the canonical Vulekamali ORM data.
KNOWN_ENTITY_ALIASES = {
    "treasury": "National Treasury",
    "nt": "National Treasury",
    "saps": "Police",
    "south african police service": "Police",
    "dha": "Home Affairs",
}

NATIONAL_DATA_MODELS = (ENEData, AENEData, BudgetVSActualNationalData)
PROVINCIAL_DATA_MODELS = (EPREData, BudgetVSActualProvincialData)


def _normalise(value: str) -> str:
    """Return a conservative comparison key without weakening matching rules."""
    value = re.sub(r"[^\w]+", " ", value.casefold(), flags=re.UNICODE)
    return " ".join(value.split())


def _canonical_name(entity: Any) -> str:
    return getattr(entity, "name", getattr(entity, "slug", str(entity)))


class EntityResolver:
    """Resolve assistant entities against published Vulekamali data.

    ``page_context`` is used only if the user did not state a sphere/province.
    Explicit query fields always take priority, preventing a provincial page
    from silently changing a national question (and vice versa).
    """

    def __init__(
        self,
        financial_year_model=FinancialYear,
        sphere_model=Sphere,
        government_model=Government,
        department_model=Department,
        programme_model=Programme,
        financial_year_resolver: Optional[FinancialYearResolver] = None,
        national_data_models: Sequence[Any] = NATIONAL_DATA_MODELS,
        provincial_data_models: Sequence[Any] = PROVINCIAL_DATA_MODELS,
        aliases: Mapping[str, str] = KNOWN_ENTITY_ALIASES,
    ):
        self.financial_year_model = financial_year_model
        self.financial_year_resolver = financial_year_resolver or FinancialYearResolver(
            financial_year_model
        )
        self.sphere_model = sphere_model
        self.government_model = government_model
        self.department_model = department_model
        self.programme_model = programme_model
        self.national_data_models = tuple(national_data_models)
        self.provincial_data_models = tuple(provincial_data_models)
        self.aliases = {_normalise(key): value for key, value in aliases.items()}

    def _resolve(self, entity_type: str, value: str, candidates: Iterable[Any]):
        candidates = list(candidates)
        normalised_value = _normalise(value)

        # A user may use the shared department family name rather than an
        # institution's full catalogue name. For example, ``Education`` must
        # include Basic Education, Higher Education and Training, and the
        # provincial Education departments. Restrict this to whole normalised
        # words and the department catalogue; it is not a broad fuzzy match.
        if entity_type == "department" and len(normalised_value) >= 5:
            topic_matches = [
                entity
                for entity in candidates
                if " {} ".format(normalised_value)
                in " {} ".format(_normalise(_canonical_name(entity)))
            ]
            if topic_matches:
                return self._from_matches(entity_type, value, topic_matches)

        exact = [
            entity
            for entity in candidates
            if value == _canonical_name(entity)
            or value == getattr(entity, "slug", None)
        ]
        if exact:
            return self._from_matches(entity_type, value, exact)

        alias_target = self.aliases.get(_normalise(value))
        if alias_target:
            aliases = [
                entity
                for entity in candidates
                if _canonical_name(entity) == alias_target
            ]
            if aliases:
                return self._from_matches(entity_type, value, aliases)

        normalised = [
            entity
            for entity in candidates
            if _normalise(_canonical_name(entity)) == normalised_value
        ]
        if normalised:
            return self._from_matches(entity_type, value, normalised)

        safe_match = self._safe_typo_match(normalised_value, candidates)
        return self._from_matches(entity_type, value, safe_match)

    @staticmethod
    def _safe_typo_match(value: str, candidates: Sequence[Any]):
        """Resolve only a unique, high-confidence catalogue spelling match.

        This is deliberately applied after canonical/alias/normalised matching
        and only to candidates already constrained by year, sphere and province.
        It improves ordinary incomplete or transposed-letter department input
        without allowing an LLM or broad fuzzy search to select an entity.
        """
        if len(value) < 6:
            return ()

        prefixes = [
            entity
            for entity in candidates
            if _normalise(_canonical_name(entity)).startswith(value)
        ]
        if len(prefixes) == 1:
            return prefixes
        if len(prefixes) > 1:
            return prefixes

        scored = sorted(
            (
                (SequenceMatcher(None, value, _normalise(_canonical_name(entity))).ratio(), entity)
                for entity in candidates
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        if not scored or scored[0][0] < 0.92:
            return ()
        if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.06:
            return ()
        return (scored[0][1],)

    @staticmethod
    def _from_matches(entity_type: str, value: str, matches: Sequence[Any]):
        unique = {}
        for match in matches:
            unique[getattr(match, "pk", _canonical_name(match))] = match
        matches = list(unique.values())
        if len(matches) == 1:
            entity = matches[0]
            return EntityResolution(
                ResolutionStatus.RESOLVED,
                entity_type,
                value,
                _canonical_name(entity),
                entity,
            )
        if not matches:
            return EntityResolution(ResolutionStatus.UNKNOWN_ENTITY, entity_type, value)
        return EntityResolution(
            ResolutionStatus.AMBIGUOUS_ENTITY,
            entity_type,
            value,
            candidates=tuple(sorted(_canonical_name(entity) for entity in matches)),
            candidate_entities=tuple(matches),
        )

    def resolve_financial_year(self, value: str) -> EntityResolution:
        resolution = self.financial_year_resolver.resolve_explicit(value)
        if resolution.status == FinancialYearResolutionStatus.RESOLVED:
            year = resolution.years[0]
            return EntityResolution(
                ResolutionStatus.RESOLVED, "financial_year", value, year.slug, year
            )
        return EntityResolution(
            ResolutionStatus.UNKNOWN_ENTITY, "financial_year", value
        )

    def resolve_sphere(self, value: str, financial_year: Any) -> EntityResolution:
        return self._resolve(
            "government_sphere",
            value,
            self.sphere_model.objects.filter(financial_year=financial_year),
        )

    def resolve_province(self, value: str, financial_year: Any) -> EntityResolution:
        return self._resolve(
            "province",
            value,
            self.government_model.objects.filter(
                sphere__financial_year=financial_year, sphere__slug="provincial"
            ),
        )

    def resolve_department(
        self,
        value: str,
        financial_year: Any,
        sphere: Optional[Any] = None,
        province: Optional[Any] = None,
        page_context: Optional[Mapping[str, Any]] = None,
    ) -> EntityResolution:
        # A named department without an explicit sphere or province is a
        # cross-sphere question. Do not let the page currently being viewed
        # silently exclude National Basic Education, Higher Education, or a
        # National/Provincial Health department. Page context is still applied
        # upstream when the user has not named a department at all.
        selected_sphere = sphere
        selected_province = province
        candidates = self.department_model.objects.filter(
            government__sphere__financial_year=financial_year
        )
        if selected_province is not None:
            candidates = candidates.filter(government=selected_province)
        elif selected_sphere is not None:
            candidates = candidates.filter(government__sphere=selected_sphere)
        return self._resolve("department", value, candidates)

    def resolve_programme(self, value: str, department: Any) -> EntityResolution:
        canonical = self._resolve(
            "programme",
            value,
            self.programme_model.objects.filter(department=department),
        )
        if canonical.status == ResolutionStatus.RESOLVED:
            return canonical
        return self._resolve_dataset_value(
            "programme", value, {"department": department.name}
        )

    def resolve_subprogramme(
        self, value: str, department: Any, programme: Optional[Any] = None
    ) -> EntityResolution:
        filters = {"department": department.name}
        if programme is not None:
            filters["programme"] = programme.name
        return self._resolve_dataset_value("subprogramme", value, filters)

    def resolve_budget_phase(
        self,
        value: str,
        financial_year: Any,
        sphere: Optional[Any] = None,
        province: Optional[Any] = None,
    ) -> EntityResolution:
        models = self._data_models(sphere=sphere, province=province)
        return self._resolve_dataset_value(
            "budget_phase",
            value,
            {"financialYear__in": source_financial_year_values(financial_year.slug)},
            models=models,
            field="budgetPhase",
        )

    def _data_models(
        self, sphere: Optional[Any] = None, province: Optional[Any] = None
    ):
        if province is not None or getattr(sphere, "slug", None) == "provincial":
            return self.provincial_data_models
        if getattr(sphere, "slug", None) == "national":
            return self.national_data_models
        return self.national_data_models + self.provincial_data_models

    def _resolve_dataset_value(
        self,
        entity_type: str,
        value: str,
        filters: Mapping[str, str],
        models: Optional[Sequence[Any]] = None,
        field: Optional[str] = None,
    ) -> EntityResolution:
        field = field or entity_type
        matches = []
        for model in models or self._data_models():
            queryset = (
                model.objects.filter(**filters).values_list(field, flat=True).distinct()
            )
            matches.extend(candidate for candidate in queryset if candidate)
        return self._resolve(
            entity_type, value, (_DatasetValue(name) for name in matches)
        )

    def validate_budget_query(
        self, query: BudgetQuery, page_context: Optional[Mapping[str, Any]] = None
    ) -> EntityValidationResult:
        """Validate the fields present in a parsed query and stop at first error."""
        resolved: Dict[str, EntityResolution] = {}

        def add(field_name: str, resolution: EntityResolution):
            resolved[field_name] = resolution
            if resolution.status != ResolutionStatus.RESOLVED:
                return EntityValidationResult(resolution.status, resolved, field_name)
            return None

        if query.financial_year:
            result = add(
                "financial_year", self.resolve_financial_year(query.financial_year)
            )
            if result:
                return result
        if query.comparison_year:
            result = add(
                "comparison_year", self.resolve_financial_year(query.comparison_year)
            )
            if result:
                return result

        year = resolved.get("financial_year")
        financial_year = year.entity if year else None
        if financial_year is None:
            return EntityValidationResult(
                ResolutionStatus.UNKNOWN_ENTITY, resolved, "financial_year"
            )

        sphere = None
        if query.entity_type in (EntityType.NATIONAL, EntityType.PROVINCIAL):
            result = add(
                "government_sphere",
                self.resolve_sphere(query.entity_type.value, financial_year),
            )
            if result:
                return result
            sphere = resolved["government_sphere"].entity

        province = None
        if query.province:
            result = add(
                "province", self.resolve_province(query.province, financial_year)
            )
            if result:
                return result
            province = resolved["province"].entity

        sphere = province.sphere if province is not None else sphere
        if query.department:
            result = add(
                "department",
                self.resolve_department(
                    query.department,
                    financial_year,
                    sphere=sphere,
                    province=province,
                    page_context=page_context,
                ),
            )
            if result:
                return result
        department = resolved.get("department")
        if query.programme:
            if not department:
                return EntityValidationResult(
                    ResolutionStatus.UNKNOWN_ENTITY, resolved, "programme"
                )
            result = add(
                "programme", self.resolve_programme(query.programme, department.entity)
            )
            if result:
                return result
        if query.subprogramme:
            if not department:
                return EntityValidationResult(
                    ResolutionStatus.UNKNOWN_ENTITY, resolved, "subprogramme"
                )
            programme = resolved.get("programme")
            result = add(
                "subprogramme",
                self.resolve_subprogramme(
                    query.subprogramme,
                    department.entity,
                    programme.entity if programme else None,
                ),
            )
            if result:
                return result

        selected_sphere = sphere or (
            department.entity.government.sphere if department else None
        )
        comparison_year = resolved.get("comparison_year")
        comparison_financial_year = (
            comparison_year.entity if comparison_year else financial_year
        )
        comparison_province = None
        if query.comparison_province:
            result = add(
                "comparison_province",
                self.resolve_province(
                    query.comparison_province, comparison_financial_year
                ),
            )
            if result:
                return result
            comparison_province = resolved["comparison_province"].entity
        comparison_sphere = (
            comparison_province.sphere
            if comparison_province is not None
            else selected_sphere
        )
        if query.comparison_department:
            result = add(
                "comparison_department",
                self.resolve_department(
                    query.comparison_department,
                    comparison_financial_year,
                    sphere=comparison_sphere,
                    province=comparison_province,
                    page_context=page_context,
                ),
            )
            if result:
                return result
        if query.budget_phase:
            result = add(
                "budget_phase",
                self.resolve_budget_phase(
                    query.budget_phase.value,
                    financial_year,
                    selected_sphere,
                    province,
                ),
            )
            if result:
                return result
        if query.comparison_phase:
            result = add(
                "comparison_phase",
                self.resolve_budget_phase(
                    query.comparison_phase.value,
                    comparison_financial_year,
                    comparison_sphere,
                    comparison_province,
                ),
            )
            if result:
                return result
        return EntityValidationResult(ResolutionStatus.RESOLVED, resolved)


@dataclass(frozen=True)
class _DatasetValue:
    name: str
