import json
from unittest.mock import patch

from django.test import SimpleTestCase

from budgetportal.views import historical_expenditure


class HistoricalExpenditureTests(SimpleTestCase):
    @patch("budgetportal.views.get_historical_expenditure")
    def test_selects_single_highest_priority_phase_per_year(self, mock_history):
        mock_history.return_value = [
            {"financialYear": "2023", "budgetPhase": "Main appropriation", "total_value": 100},
            {"financialYear": "2023", "budgetPhase": "Audit Outcome", "total_value": 90},
            {"financialYear": "2024", "budgetPhase": "Adjusted appropriation", "total_value": 120},
            {"financialYear": "2024", "budgetPhase": "Main appropriation", "total_value": 110},
        ]

        result = json.loads(historical_expenditure("Example Department", "National"))

        self.assertEqual(
            result["children"],
            [
                {
                    "Name": "2023",
                    "Count": 90.0,
                    "BudgetPhase": "Audit Outcome",
                    "SeriesType": "historical",
                },
                {
                    "Name": "2024",
                    "Count": 120.0,
                    "BudgetPhase": "Adjusted appropriation",
                    "SeriesType": "planned",
                },
            ],
        )
