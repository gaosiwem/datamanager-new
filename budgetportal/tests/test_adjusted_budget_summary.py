import json

from django.test import SimpleTestCase
from mock import Mock, patch

from budgetportal.views import get_adjusted_budget_summary


class AdjustedBudgetSummaryTests(SimpleTestCase):
    @patch("budgetportal.views.AENEData.objects.filter")
    def test_returns_none_when_no_adjusted_budget_rows_exist(self, mock_filter):
        mock_queryset = Mock()
        mock_queryset.values.return_value = []
        mock_filter.return_value = mock_queryset

        result = get_adjusted_budget_summary("2026-27", "Example Department")

        self.assertIsNone(result)

    @patch("budgetportal.views.AENEData.objects.filter")
    def test_chart_data_uses_adjustments_without_double_counting_budgets(self, mock_filter):
        rows = [
            {
                "amountKind": "Total",
                "budgetPhase": "Appropriation",
                "programme": "Programme A",
                "subprogramme": "Subprogramme A",
                "economicClassification2": "Current payments",
                "economicClassification3": "Goods and services",
                "value": 1000,
            },
            {
                "amountKind": "Total",
                "budgetPhase": "Announced in the budget speech",
                "programme": "Programme A",
                "subprogramme": "Subprogramme A",
                "economicClassification2": "Transfers and subsidies",
                "economicClassification3": "Provinces and municipalities",
                "value": 100,
            },
            {
                "amountKind": "Total",
                "budgetPhase": "Roll-overs",
                "programme": "Programme B",
                "subprogramme": "Subprogramme B",
                "economicClassification2": "Payments for capital assets",
                "economicClassification3": "Machinery and equipment",
                "value": 50,
            },
            {
                "amountKind": "Total",
                "budgetPhase": "Total adjustments",
                "programme": "Programme A",
                "subprogramme": "Subprogramme A",
                "economicClassification2": "Transfers and subsidies",
                "economicClassification3": "Provinces and municipalities",
                "value": 100,
            },
            {
                "amountKind": "Total",
                "budgetPhase": "Total adjustments",
                "programme": "Programme B",
                "subprogramme": "Subprogramme B",
                "economicClassification2": "Payments for capital assets",
                "economicClassification3": "Machinery and equipment",
                "value": 50,
            },
            {
                "amountKind": "Total",
                "budgetPhase": "Adjusted appropriation",
                "programme": "Programme A",
                "subprogramme": "Subprogramme A",
                "economicClassification2": "Current payments",
                "economicClassification3": "Goods and services",
                "value": 1150,
            },
        ]
        mock_queryset = Mock()
        mock_queryset.values.return_value = rows
        mock_filter.return_value = mock_queryset

        result = get_adjusted_budget_summary("2024-25", "Example Department")

        mock_filter.assert_called_once_with(
            department="Example Department",
            financialYear="2024",
            amountKind="Total",
        )
        self.assertEqual(
            {item["name"]: item["value"] for item in json.loads(result["by_type"])},
            {
                "Announced in the budget speech": 100.0,
                "Roll-overs": 50.0,
            },
        )
        self.assertEqual(
            {item["name"]: item["value"] for item in json.loads(result["programmes"])},
            {"Programme A": 100.0, "Programme B": 50.0},
        )
        self.assertEqual(
            {item["name"]: item["value"] for item in json.loads(result["econ_classes"])},
            {
                "Transfers and subsidies": 100.0,
                "Payments for capital assets": 50.0,
            },
        )
        self.assertEqual(result["total_change"]["amount"], 150.0)
