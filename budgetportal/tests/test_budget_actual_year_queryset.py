from decimal import Decimal

from django.db.models import Sum
from django.test import TestCase

from budgetportal.models import BudgetVSActualProvincialData
from budgetportal.views import provincial_budget_year_queryset


class ProvincialBudgetYearQuerysetTests(TestCase):
    def make_row(self, **overrides):
        defaults = {
            "government": "Gauteng",
            "voteNumber": 1,
            "department": "Education",
            "progNumber": 1,
            "programme": "Programme 1",
            "subprogNumber": "1",
            "subprogramme": "Subprogramme 1",
            "economicClassification1": "Current payments",
            "economicClassification2": "Compensation of employees",
            "economicClassification3": "Salaries",
            "economicClassification4": "Level 4",
            "economicClassification5": "Level 5",
            "functionGroup1": "Learning and culture",
            "budgetYear": None,
            "financialYear": "2025",
            "budgetPhase": "Main appropriation",
            "amountKind": "Budget",
            "value": Decimal("100"),
        }
        defaults.update(overrides)
        return BudgetVSActualProvincialData.objects.create(**defaults)

    def test_prefers_untagged_main_appropriation_rows(self):
        self.make_row(value=Decimal("100"))
        self.make_row(budgetYear="2025", value=Decimal("200"))

        total = provincial_budget_year_queryset("2025").aggregate(total=Sum("value"))["total"]

        self.assertEqual(total, Decimal("100"))

    def test_falls_back_to_baseline_when_main_appropriation_missing(self):
        self.make_row(
            financialYear="2026",
            budgetPhase="Baseline",
            value=Decimal("300"),
        )

        total = provincial_budget_year_queryset("2026").aggregate(total=Sum("value"))["total"]

        self.assertEqual(total, Decimal("300"))
