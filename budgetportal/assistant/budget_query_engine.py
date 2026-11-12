"""Deterministic budget queries over the authoritative Vulekamali ORM rows."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Mapping, Optional, Sequence

from django.db.models import Sum

from budgetportal.assistant.financial_year_resolver import source_financial_year_values
from budgetportal.assistant.schemas import (
    BudgetPhase,
    BudgetQuery,
    DirectChargeScope,
    EntityType,
    GroupBy,
    Intent,
    Metric,
)
from budgetportal.models import (
    AENEData,
    BudgetVSActualNationalData,
    BudgetVSActualProvincialData,
    ENEData,
    EPREData,
)
from budgetportal.models.government import DIRECT_CHARGE_NRF


OK = "ok"
NO_MATCHING_SOURCE_RECORDS = "no_matching_source_records"
NEEDS_BUDGET_PHASE = "needs_budget_phase"
UNSUPPORTED_VARIANCE_DEFINITION = "unsupported_variance_definition"

GROUP_FIELDS = {
    GroupBy.DEPARTMENT: "department",
    GroupBy.PROVINCE: "government",
    GroupBy.PROGRAMME: "programme",
    GroupBy.SUBPROGRAMME: "subprogramme",
    GroupBy.ECONOMIC_CLASSIFICATION_2: "economicClassification2",
    GroupBy.ECONOMIC_CLASSIFICATION_3: "economicClassification3",
    GroupBy.FINANCIAL_YEAR: "financialYear",
}


@dataclass(frozen=True)
class BudgetQueryResult:
    status: str
    intent: str
    entities: Mapping[str, Optional[str]] = field(default_factory=dict)
    financial_year: Optional[str] = None
    comparison_year: Optional[str] = None
    budget_phase: Optional[str] = None
    comparison_phase: Optional[str] = None
    values: Sequence[Mapping[str, Any]] = ()
    calculations: Mapping[str, Any] = field(default_factory=dict)
    source_metadata: Sequence[Mapping[str, Any]] = ()


@dataclass(frozen=True)
class _Measurement:
    value: Optional[Decimal]
    record_count: int
    metadata: Mapping[str, Any]


class BudgetQueryEngine:
    """Execute pre-validated queries with fixed ORM filters and Decimal math.

    No caller-provided text is used as SQL.  The engine intentionally requires
    an exact phase for ordinary amounts, rankings and trends: aggregating more
    than one phase would double count a vote and silently change the question.
    """

    def __init__(
        self,
        national_model=BudgetVSActualNationalData,
        provincial_model=BudgetVSActualProvincialData,
        national_primary_model=ENEData,
        provincial_primary_model=EPREData,
        national_adjusted_model=AENEData,
    ):
        self.national_model = national_model
        self.provincial_model = provincial_model
        self.national_primary_model = national_primary_model
        self.provincial_primary_model = provincial_primary_model
        self.national_adjusted_model = national_adjusted_model

    def execute(self, query: BudgetQuery) -> BudgetQueryResult:
        handlers = {
            Intent.AMOUNT_LOOKUP: self.amount_lookup,
            Intent.VARIANCE_ANALYSIS: self.variance_analysis,
            Intent.COMPARISON: self.comparison,
            Intent.RANKING: self.ranking,
            Intent.TREND_ANALYSIS: self.trend_analysis,
            Intent.PERCENTAGE_CHANGE: self.percentage_change,
        }
        return handlers[query.intent](query)

    def catalogue_values(self, query: BudgetQuery, field: str):
        """List published dimension values without choosing a budget phase."""
        allowed_fields = {
            "programme",
            "subprogramme",
            "economicClassification1",
            "economicClassification2",
            "economicClassification3",
            "functionGroup1",
        }
        if field not in allowed_fields:
            raise ValueError("Unsupported catalogue field.")
        is_provincial = bool(
            query.province or query.entity_type == EntityType.PROVINCIAL
        )
        primary_model = (
            self.provincial_primary_model if is_provincial else self.national_primary_model
        )
        secondary_model = (
            self.provincial_model if is_provincial else self.national_model
        )
        filters = {"financialYear__in": source_financial_year_values(query.financial_year)}
        for query_field in ("department", "programme", "subprogramme"):
            if query_field == field:
                continue
            value = getattr(query, query_field)
            if value:
                filters[query_field] = value
        if query.province:
            filters["government"] = query.province

        queryset = primary_model.objects.filter(**filters)
        if not queryset.exists():
            queryset = secondary_model.objects.filter(**filters)
        return tuple(
            queryset.exclude(**{field: ""})
            .exclude(**{"{}__isnull".format(field): True})
            .values_list(field, flat=True)
            .distinct()
            .order_by(field)[:100]
        )

    def amount_lookup(self, query: BudgetQuery) -> BudgetQueryResult:
        if query.budget_phase is None:
            return self._phase_required(query)
        measurement = self._measure(query, query.financial_year, query.budget_phase)
        if (
            measurement.metadata.get("aene_source_fallback")
            and query.budget_phase == BudgetPhase.TOTAL_ADJUSTMENTS
            and query.direct_charge_scope is None
        ):
            components = self._aene_total_adjustment_components(
                query, query.financial_year, query.budget_phase
            )
            if len(components) > 1:
                return self._result(
                    query,
                    OK,
                    values=components,
                    source_metadata=(measurement.metadata,),
                )
        return self._single_measurement_result(query, measurement)

    def variance_analysis(self, query: BudgetQuery) -> BudgetQueryResult:
        phases = (query.budget_phase, query.comparison_phase)
        expected = (BudgetPhase.FINAL_APPROPRIATION, BudgetPhase.AUDIT_OUTCOME)
        if phases not in ((None, None), expected):
            return self._result(query, UNSUPPORTED_VARIANCE_DEFINITION)
        final = self._measure(
            query, query.financial_year, BudgetPhase.FINAL_APPROPRIATION
        )
        actual = self._measure(query, query.financial_year, BudgetPhase.AUDIT_OUTCOME)
        if final.value is None or actual.value is None:
            return self._result(
                query,
                NO_MATCHING_SOURCE_RECORDS,
                budget_phase=BudgetPhase.FINAL_APPROPRIATION.value,
                comparison_phase=BudgetPhase.AUDIT_OUTCOME.value,
                source_metadata=(final.metadata, actual.metadata),
            )
        variance = final.value - actual.value
        percentage = self._percentage(variance, final.value)
        return self._result(
            query,
            OK,
            budget_phase=BudgetPhase.FINAL_APPROPRIATION.value,
            comparison_phase=BudgetPhase.AUDIT_OUTCOME.value,
            values=(
                {"label": "Final Appropriation", "amount": final.value},
                {"label": "Audit Outcome", "amount": actual.value},
            ),
            calculations={
                "variance": variance,
                "percentage_variance": percentage,
                "denominator_zero": final.value == Decimal("0"),
            },
            source_metadata=(final.metadata, actual.metadata),
        )

    def comparison(self, query: BudgetQuery) -> BudgetQueryResult:
        if query.budget_phase is None:
            return self._phase_required(query)
        comparison_phase = query.comparison_phase or query.budget_phase
        first = self._measure(query, query.financial_year, query.budget_phase)
        alternate = self._copy_query(
            query,
            department=query.comparison_department or query.department,
            province=query.comparison_province or query.province,
        )
        second = self._measure(
            alternate,
            query.comparison_year or query.financial_year,
            comparison_phase,
        )
        if first.value is None or second.value is None:
            return self._result(
                query,
                NO_MATCHING_SOURCE_RECORDS,
                comparison_year=query.comparison_year or query.financial_year,
                comparison_phase=comparison_phase.value,
                source_metadata=(first.metadata, second.metadata),
            )
        return self._result(
            query,
            OK,
            comparison_year=query.comparison_year or query.financial_year,
            comparison_phase=comparison_phase.value,
            values=(
                {"label": "primary", "amount": first.value},
                {"label": "comparison", "amount": second.value},
            ),
            calculations={"difference": first.value - second.value},
            source_metadata=(first.metadata, second.metadata),
        )

    def ranking(self, query: BudgetQuery) -> BudgetQueryResult:
        if query.budget_phase is None:
            return self._phase_required(query)
        group_field = GROUP_FIELDS.get(query.group_by)
        if group_field is None:
            return self._result(query, NO_MATCHING_SOURCE_RECORDS)
        queryset, filters = self._source_queryset(
            query, query.financial_year, query.budget_phase
        )
        # Ranking a dimension must not retain a filter for that same dimension.
        filters.pop(group_field, None)
        queryset = queryset.filter(**filters).exclude(**{group_field: ""})
        ordering = (
            ("-total", group_field) if query.descending else ("total", group_field)
        )
        rows = list(
            queryset.values(group_field)
            .annotate(total=Sum("value"))
            .order_by(*ordering)[: query.limit or 10]
        )
        metadata = self._metadata(
            queryset, query, query.financial_year, query.budget_phase, filters
        )
        if not rows:
            return self._result(
                query, NO_MATCHING_SOURCE_RECORDS, source_metadata=(metadata,)
            )
        return self._result(
            query,
            OK,
            values=tuple(
                {"entity": row[group_field], "amount": row["total"]} for row in rows
            ),
            source_metadata=(metadata,),
        )

    def trend_analysis(self, query: BudgetQuery) -> BudgetQueryResult:
        if query.budget_phase is None:
            return self._phase_required(query)
        years = self._trend_years(query.financial_year, query.comparison_year)
        observations, metadata = [], []
        for year in years:
            measurement = self._measure(query, year, query.budget_phase)
            observations.append({"financial_year": year, "amount": measurement.value})
            metadata.append(measurement.metadata)
        if not any(item["amount"] is not None for item in observations):
            return self._result(
                query,
                NO_MATCHING_SOURCE_RECORDS,
                values=tuple(observations),
                source_metadata=tuple(metadata),
            )
        return self._result(
            query, OK, values=tuple(observations), source_metadata=tuple(metadata)
        )

    def percentage_change(self, query: BudgetQuery) -> BudgetQueryResult:
        if query.budget_phase is None:
            return self._phase_required(query)
        comparison_phase = query.comparison_phase or query.budget_phase
        old = self._measure(query, query.financial_year, query.budget_phase)
        alternate = self._copy_query(
            query,
            department=query.comparison_department or query.department,
            province=query.comparison_province or query.province,
        )
        new = self._measure(alternate, query.comparison_year, comparison_phase)
        if old.value is None or new.value is None:
            return self._result(
                query,
                NO_MATCHING_SOURCE_RECORDS,
                source_metadata=(old.metadata, new.metadata),
            )
        difference = new.value - old.value
        return self._result(
            query,
            OK,
            comparison_phase=comparison_phase.value,
            values=(
                {"label": "old", "amount": old.value},
                {"label": "new", "amount": new.value},
            ),
            calculations={
                "difference": difference,
                "percentage_change": self._percentage(difference, old.value),
                "denominator_zero": old.value == Decimal("0"),
            },
            source_metadata=(old.metadata, new.metadata),
        )

    def _measure(self, query, financial_year, budget_phase) -> _Measurement:
        queryset, filters = self._source_queryset(query, financial_year, budget_phase)
        queryset = queryset.filter(**filters)
        record_count = queryset.count()
        fallback_source = None
        if (
            record_count == 0
            and budget_phase == BudgetPhase.MAIN_APPROPRIATION
        ):
            queryset, filters = self._primary_source_queryset(
                query, financial_year, budget_phase
            )
            queryset = queryset.filter(**filters)
            record_count = queryset.count()
            fallback_source = "primary" if record_count else None
        elif (
            record_count == 0
            and budget_phase
            in (
                BudgetPhase.ADJUSTED_APPROPRIATION,
                BudgetPhase.TOTAL_ADJUSTMENTS,
            )
            and not self._is_provincial_query(query)
        ):
            queryset, filters = self._national_adjusted_source_queryset(
                query, financial_year, budget_phase
            )
            queryset = queryset.filter(**filters)
            record_count = queryset.count()
            fallback_source = "aene" if record_count else None
        total = (
            queryset.aggregate(total=Sum("value"))["total"] if record_count else None
        )
        metadata = self._metadata(
            queryset, query, financial_year, budget_phase, filters, record_count
        )
        if fallback_source == "primary":
            metadata["primary_source_fallback"] = True
        elif fallback_source == "aene":
            metadata["aene_source_fallback"] = True
        return _Measurement(
            total,
            record_count,
            metadata,
        )

    def _source_queryset(self, query, financial_year, budget_phase):
        is_provincial = self._is_provincial_query(query)
        model = self.provincial_model if is_provincial else self.national_model
        queryset = model.objects.all()
        filters: Dict[str, Any] = {
            "financialYear__in": source_financial_year_values(financial_year),
            "budgetPhase": budget_phase.value,
        }
        for query_field, source_field in (
            ("department", "department"),
            ("programme", "programme"),
            ("subprogramme", "subprogramme"),
        ):
            value = getattr(query, query_field)
            if value:
                filters[source_field] = value
        if query.province:
            filters["government"] = query.province
        if query.direct_charge_scope == DirectChargeScope.DIRECT_CHARGES:
            filters["programme"] = DIRECT_CHARGE_NRF
        elif query.direct_charge_scope == DirectChargeScope.VOTED:
            filters["programme__ne"] = DIRECT_CHARGE_NRF
        # Django cannot express ``__ne``. Keep the intention separate until
        # the ORM queryset is built below.
        if "programme__ne" in filters:
            direct_charge = filters.pop("programme__ne")
            queryset = queryset.exclude(programme=direct_charge)
        if any(field.name == "amountKind" for field in model._meta.fields):
            amount_kind = self._select_amount_kind(
                queryset,
                filters,
                query.metric,
                budget_phase,
            )
            if amount_kind:
                filters["amountKind"] = amount_kind
        return queryset, filters

    def _primary_source_queryset(self, query, financial_year, budget_phase):
        """Use the primary ENE/EPRE import only if BVA has no main-budget row.

        Budget-vs-Actual data remains the preferred source because it supports
        phase and actual comparisons.  New financial years can, however, have
        an EPRE or ENE main appropriation before the paired BVA extract contains
        that phase.  Falling back only for a missing Main appropriation prevents
        an ambiguous department from being hidden despite published primary data.
        """
        is_provincial = self._is_provincial_query(query)
        model = (
            self.provincial_primary_model if is_provincial else self.national_primary_model
        )
        queryset = model.objects.all()
        filters: Dict[str, Any] = {
            "financialYear__in": source_financial_year_values(financial_year),
            "budgetPhase": budget_phase.value,
        }
        for query_field, source_field in (
            ("department", "department"),
            ("programme", "programme"),
            ("subprogramme", "subprogramme"),
        ):
            value = getattr(query, query_field)
            if value:
                filters[source_field] = value
        if query.province:
            filters["government"] = query.province
        if query.direct_charge_scope == DirectChargeScope.DIRECT_CHARGES:
            filters["programme"] = DIRECT_CHARGE_NRF
        elif query.direct_charge_scope == DirectChargeScope.VOTED:
            queryset = queryset.exclude(programme=DIRECT_CHARGE_NRF)
        return queryset, filters

    def _national_adjusted_source_queryset(self, query, financial_year, budget_phase):
        """Use AENE only for national adjusted-budget lookups.

        Budget-vs-Actual remains preferred whenever it has matching rows. AENE
        is the authoritative national source for adjusted appropriation and
        total adjustments when that paired extract is absent.
        """
        queryset = self.national_adjusted_model.objects.all()
        filters: Dict[str, Any] = {
            "financialYear__in": source_financial_year_values(financial_year),
            "budgetPhase": budget_phase.value,
        }
        for query_field, source_field in (
            ("department", "department"),
            ("programme", "programme"),
            ("subprogramme", "subprogramme"),
        ):
            value = getattr(query, query_field)
            if value:
                filters[source_field] = value
        if query.direct_charge_scope == DirectChargeScope.DIRECT_CHARGES:
            filters["programme"] = DIRECT_CHARGE_NRF
        elif query.direct_charge_scope == DirectChargeScope.VOTED:
            queryset = queryset.exclude(programme=DIRECT_CHARGE_NRF)
        amount_kind = self._select_amount_kind(
            queryset,
            filters,
            query.metric,
            budget_phase,
            aggregate_components=True,
        )
        if amount_kind:
            filters["amountKind"] = amount_kind
        return queryset, filters

    def _aene_total_adjustment_components(self, query, financial_year, budget_phase):
        """Return published AENE adjustment components without combining them."""
        queryset, filters = self._national_adjusted_source_queryset(
            query, financial_year, budget_phase
        )
        rows = (
            queryset.filter(**filters)
            .exclude(amountKind="")
            .values("amountKind")
            .annotate(total=Sum("value"))
            .order_by("amountKind")
        )
        return tuple(
            {"label": row["amountKind"], "amount": row["total"]} for row in rows
        )

    @staticmethod
    def _is_provincial_query(query):
        return bool(
            query.province
            or query.entity_type == EntityType.PROVINCIAL
            or query.group_by == GroupBy.PROVINCE
        )

    @staticmethod
    def _amount_kind(metric: Optional[Metric], phase: BudgetPhase) -> Optional[str]:
        if metric == Metric.ACTUAL or phase == BudgetPhase.AUDIT_OUTCOME:
            return "Actual"
        if metric in (None, Metric.BUDGET, Metric.ADJUSTED_BUDGET, Metric.VALUE):
            return "Budget"
        return "Budget"

    def _select_amount_kind(
        self, queryset, filters, metric, phase, aggregate_components=False
    ):
        """Choose a non-duplicated source representation.

        Existing Budget-vs-Actual imports commonly label an already-totalled
        vote as ``Total``. Older fixtures/imports use ``Budget`` or ``Actual``
        instead. Prefer Total only when it exists for the exact deterministic
        filters. AENE adjustment data without a Total row retains its published
        components so an amount lookup can show them separately.
        """
        available = set(
            queryset.filter(**filters)
            .exclude(amountKind="")
            .values_list("amountKind", flat=True)
            .distinct()
        )
        if "Total" in available:
            return "Total"
        if aggregate_components:
            return None
        return self._amount_kind(metric, phase)

    @staticmethod
    def _percentage(numerator: Decimal, denominator: Decimal) -> Optional[Decimal]:
        if denominator == Decimal("0"):
            return None
        return numerator / denominator * Decimal("100")

    @staticmethod
    def _trend_years(start: str, end: Optional[str]):
        if not end:
            return (start,)
        first, last = int(start[:4]), int(end[:4])
        return tuple(
            "{}-{:02d}".format(year, (year + 1) % 100)
            for year in range(first, last + 1)
        )

    @staticmethod
    def _copy_query(query: BudgetQuery, **values):
        data = query.to_dict()
        data.update(values)
        return BudgetQuery.from_dict(data)

    def _single_measurement_result(self, query, measurement):
        if measurement.value is None:
            return self._result(
                query,
                NO_MATCHING_SOURCE_RECORDS,
                source_metadata=(measurement.metadata,),
            )
        return self._result(
            query,
            OK,
            values=({"amount": measurement.value},),
            source_metadata=(measurement.metadata,),
        )

    def _phase_required(self, query):
        return self._result(query, NEEDS_BUDGET_PHASE)

    def _result(self, query, status, **values):
        payload = {
            "status": status,
            "intent": query.intent.value,
            "entities": {
                "department": query.department,
                "comparison_department": query.comparison_department,
                "province": query.province,
                "comparison_province": query.comparison_province,
                "programme": query.programme,
                "subprogramme": query.subprogramme,
            },
            "financial_year": query.financial_year,
            "comparison_year": query.comparison_year,
            "budget_phase": query.budget_phase.value if query.budget_phase else None,
            "comparison_phase": query.comparison_phase.value
            if query.comparison_phase
            else None,
        }
        payload.update(values)
        return BudgetQueryResult(**payload)

    @staticmethod
    def _metadata(queryset, query, financial_year, phase, filters, record_count=None):
        return {
            "model": queryset.model._meta.label,
            "financial_year": financial_year,
            "budget_phase": phase.value,
            "filters": dict(filters),
            "direct_charge_scope": query.direct_charge_scope.value
            if query.direct_charge_scope
            else DirectChargeScope.ALL.value,
            "record_count": record_count
            if record_count is not None
            else queryset.count(),
            "source_financial_year_values": source_financial_year_values(
                financial_year
            ),
        }
