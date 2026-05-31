from django.test import Client, TestCase
from mock import patch

from budgetportal.models import FinancialYear


class SearchApiTestCase(TestCase):
    def setUp(self):
        FinancialYear.objects.create(slug="2025-26", published=True)
        FinancialYear.objects.create(slug="2026-27", published=True)
        self.client = Client()

    @patch("budgetportal.search_api.build_search_landing_results")
    def test_search_landing_api_returns_cached_shape(self, build_search_landing_results):
        build_search_landing_results.return_value = {
            "count": 2,
            "items": {
                "departments": {"count": 1, "items": [], "otherYears": []},
                "datasets": {"count": 1, "items": [], "otherYears": []},
            },
        }

        response = self.client.get("/api/v1/search/", {"q": "ENE", "year": "2026-27"})

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "count": 2,
                "items": {
                    "departments": {"count": 1, "items": [], "otherYears": []},
                    "datasets": {"count": 1, "items": [], "otherYears": []},
                },
            },
        )
        build_search_landing_results.assert_called_once_with("ENE", "2026-27")

    @patch("budgetportal.search_api.build_search_landing_results")
    def test_search_landing_api_short_circuits_blank_phrase(self, build_search_landing_results):
        response = self.client.get("/api/v1/search/", {"q": "   ", "year": "2026-27"})

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "count": 0,
                "items": {
                    "departments": {"count": 0, "items": [], "otherYears": []},
                    "datasets": {"count": 0, "items": [], "otherYears": []},
                },
            },
        )
        build_search_landing_results.assert_not_called()

    @patch("budgetportal.search_api.build_search_facet_results")
    def test_search_facet_api_returns_supported_tab(self, build_search_facet_results):
        build_search_facet_results.return_value = {
            "count": 4,
            "datasets": {"count": 4, "items": [{"title": "ENE dataset"}]},
        }

        response = self.client.get(
            "/api/v1/search/facet/",
            {"q": "ENE", "year": "2026-27", "view": "datasets", "start": "0"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "count": 4,
                "datasets": {"count": 4, "items": [{"title": "ENE dataset"}]},
            },
        )
        build_search_facet_results.assert_called_once_with("ENE", "2026-27", "datasets", start=0)

    def test_search_facet_api_rejects_unsupported_tab(self):
        response = self.client.get(
            "/api/v1/search/facet/",
            {"q": "ENE", "year": "2026-27", "view": "contributed"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {"error": "Unsupported search view"})
