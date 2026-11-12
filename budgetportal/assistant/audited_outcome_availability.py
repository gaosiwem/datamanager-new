"""Determine which audited-outcome years are valid for a selected budget year."""

import re

from django.core.cache import cache

from budgetportal.models import BudgetVSActualNationalData, BudgetVSActualProvincialData


AUDIT_PHASES = ("Audit Outcome", "Audited outcome")
_SOURCE_YEAR = re.compile(r"^\d{4}$")
_CANONICAL_YEAR = re.compile(r"^\d{4}-\d{2}$")


class AuditedOutcomeAvailability:
    """Use published source rows, never an assumed calendar-year offset alone."""

    def __init__(
        self,
        national_model=BudgetVSActualNationalData,
        provincial_model=BudgetVSActualProvincialData,
        cache_backend=cache,
    ):
        self.national_model = national_model
        self.provincial_model = provincial_model
        self.cache = cache_backend

    def available_for(self, selected_financial_year, sphere=None):
        """Return published audit years at least two years behind the selection."""
        sphere_slug = getattr(sphere, "slug", sphere) or "all"
        cache_key = "assistant:audit-outcome-years:{}:{}".format(
            selected_financial_year, sphere_slug
        )
        try:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return tuple(cached)
        except Exception:
            cached = None

        models = self._models_for(sphere_slug)
        values = set()
        for model in models:
            values.update(
                model.objects.filter(budgetPhase__in=AUDIT_PHASES)
                .values_list("financialYear", flat=True)
                .distinct()
            )
        years = self.from_source_years(selected_financial_year, values)
        try:
            self.cache.set(cache_key, years, timeout=3600)
        except Exception:
            pass
        return years

    def _models_for(self, sphere):
        if sphere == "national":
            return (self.national_model,)
        if sphere == "provincial":
            return (self.provincial_model,)
        return (self.national_model, self.provincial_model)

    @staticmethod
    def from_source_years(selected_financial_year, source_years):
        """Normalise legacy source years and apply the two-year availability rule."""
        if not _CANONICAL_YEAR.fullmatch(selected_financial_year):
            return ()
        latest_start_year = int(selected_financial_year[:4]) - 2
        canonical = set()
        for value in source_years:
            if _SOURCE_YEAR.fullmatch(value):
                start = int(value)
                canonical.add("{}-{:02d}".format(start, (start + 1) % 100))
            elif _CANONICAL_YEAR.fullmatch(value):
                canonical.add(value)
        return tuple(
            sorted(
                (year for year in canonical if int(year[:4]) <= latest_start_year),
                reverse=True,
            )
        )
