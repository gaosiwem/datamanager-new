"""Deterministic interpretation of South African government financial years.

This component resolves time references only.  It performs no financial
calculation. A four-digit year is the standard shorthand for the financial
year beginning in that year (for example, ``2024`` means ``2024-25``).
``FinancialYear.published`` is Vulekamali's existing public availability
catalogue, so an unpublished or absent year is not available to the assistant.
"""

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Optional, Tuple

from budgetportal.models.government import FinancialYear


FINANCIAL_YEAR_PATTERN = re.compile(r"\b(\d{4}-\d{2})\b")
CALENDAR_YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
RANGE_CONNECTOR_PATTERN = re.compile(r"\b(?:to|through|until)\b", re.IGNORECASE)


def source_financial_year_values(financial_year: str) -> Tuple[str, ...]:
    """Return the exact year encodings used by existing Vulekamali sources.

    Public assistant input and output always use ``YYYY-YY``.  Some legacy
    Vulekamali financial tables instead store the start year (for example
    ``2023`` for the 2023-24 financial year), so deterministic source filters
    must accommodate both documented representations.
    """
    if FINANCIAL_YEAR_PATTERN.fullmatch(financial_year):
        return (financial_year, financial_year[:4])
    return (financial_year,)


class FinancialYearResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNAVAILABLE_FINANCIAL_YEAR = "unavailable_financial_year"


@dataclass(frozen=True)
class FinancialYearResolution:
    status: FinancialYearResolutionStatus
    requested_text: str
    financial_years: Tuple[str, ...] = ()
    years: Tuple[Any, ...] = ()
    reason: str = ""


class FinancialYearResolver:
    """Resolve only unambiguous, available South African financial years.

    A four-digit start year is resolved as its corresponding financial year.
    Relative ``previous financial year`` is resolved only when the caller
    deliberately supplies ``reference_financial_year`` (for example, a
    documented report context).  Calendar years, ``last year``, and rolling
    durations remain clarification cases because none identifies a unique
    government financial year on its own.
    """

    def __init__(self, financial_year_model=FinancialYear):
        self.financial_year_model = financial_year_model

    def resolve_explicit(self, value: str) -> FinancialYearResolution:
        """Validate a canonical or four-digit-start-year value against published data."""
        value = value.strip() if isinstance(value, str) else value
        if isinstance(value, str) and CALENDAR_YEAR_PATTERN.fullmatch(value):
            start_year = int(value)
            return self._available(
                value, ("{}-{:02d}".format(start_year, (start_year + 1) % 100),)
            )
        if not self._is_canonical(value):
            return self._clarification(value, "Use a financial year such as 2024-25.")
        return self._available(value, (value,))

    def resolve(
        self, text: str, reference_financial_year: Optional[str] = None
    ) -> FinancialYearResolution:
        explicit_years = tuple(FINANCIAL_YEAR_PATTERN.findall(text))
        if explicit_years:
            if len(explicit_years) == 2 and RANGE_CONNECTOR_PATTERN.search(text):
                return self._resolve_range(text, explicit_years[0], explicit_years[1])
            return self._available(text, explicit_years)

        calendar_years = tuple(CALENDAR_YEAR_PATTERN.findall(text))
        if len(calendar_years) == 1:
            return self.resolve_explicit(calendar_years[0])

        normalised = " ".join(text.casefold().split())
        if "previous financial year" in normalised:
            if reference_financial_year is None:
                return self._clarification(
                    text,
                    "Specify the financial year from which 'previous financial year' is measured.",
                )
            reference = self.resolve_explicit(reference_financial_year)
            if reference.status != FinancialYearResolutionStatus.RESOLVED:
                return FinancialYearResolution(
                    reference.status, text, reason=reference.reason
                )
            return self._available(
                text, (self._previous(reference.financial_years[0]),)
            )

        if "last year" in normalised:
            return self._clarification(
                text,
                "Specify a financial year; 'last year' may mean a calendar or financial year.",
            )
        if re.search(r"\b(?:over|last)\s+five\s+years\b", normalised):
            return self._clarification(
                text, "Specify the financial-year range for the five-year trend."
            )
        if calendar_years:
            return self._clarification(
                text,
                "A calendar year does not identify a single South African financial year.",
            )
        return self._clarification(
            text, "Specify a Vulekamali financial year such as 2024-25."
        )

    def _resolve_range(
        self, text: str, start: str, end: str
    ) -> FinancialYearResolution:
        if not self._is_canonical(start) or not self._is_canonical(end):
            return self._clarification(
                text, "Use consecutive financial-year values such as 2023-24."
            )
        start_year = int(start[:4])
        end_year = int(end[:4])
        if end_year < start_year:
            return self._clarification(
                text, "The financial-year range must run forward in time."
            )
        years = tuple(
            "{}-{:02d}".format(year, (year + 1) % 100)
            for year in range(start_year, end_year + 1)
        )
        return self._available(text, years)

    @staticmethod
    def _previous(value: str) -> str:
        start = int(value[:4]) - 1
        return "{}-{:02d}".format(start, (start + 1) % 100)

    @staticmethod
    def _is_canonical(value: str) -> bool:
        match = FINANCIAL_YEAR_PATTERN.fullmatch(value)
        return bool(match) and int(value[-2:]) == (int(value[:4]) + 1) % 100

    def _available(
        self, requested_text: str, values: Tuple[str, ...]
    ) -> FinancialYearResolution:
        if any(not self._is_canonical(value) for value in values):
            return self._clarification(
                requested_text, "Use consecutive financial-year values such as 2023-24."
            )
        # De-duplicate while retaining user-supplied/range order.
        values = tuple(dict.fromkeys(values))
        published = {
            year.slug: year
            for year in self.financial_year_model.objects.filter(
                published=True, slug__in=values
            )
        }
        unavailable = tuple(value for value in values if value not in published)
        if unavailable:
            return FinancialYearResolution(
                FinancialYearResolutionStatus.UNAVAILABLE_FINANCIAL_YEAR,
                requested_text,
                financial_years=unavailable,
                reason="The requested financial year is not available in Vulekamali.",
            )
        return FinancialYearResolution(
            FinancialYearResolutionStatus.RESOLVED,
            requested_text,
            financial_years=values,
            years=tuple(published[value] for value in values),
        )

    @staticmethod
    def _clarification(requested_text: str, reason: str) -> FinancialYearResolution:
        return FinancialYearResolution(
            FinancialYearResolutionStatus.NEEDS_CLARIFICATION,
            requested_text,
            reason=reason,
        )
