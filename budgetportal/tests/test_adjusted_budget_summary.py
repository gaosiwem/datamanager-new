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
