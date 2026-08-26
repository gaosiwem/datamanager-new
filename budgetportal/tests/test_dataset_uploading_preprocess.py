from django.test import SimpleTestCase, TestCase
from mock import Mock
from tablib import Dataset

from budgetportal.dataset_uploading import preprocess
from budgetportal.dataset_uploading.dataset_preprocessor import (
    BUDGET_ACTUAL_HEADERS,
    EPRE_HEADERS,
    get_or_create_dataset_category,
    import_dataset,
    load_tablib_dataset,
    safe_bulk_create_batch_size,
)
from budgetportal.models import DatasetCategory


class DatasetUploadingPreprocessTest(SimpleTestCase):
    def test_load_tablib_dataset_uses_tablib_dataset_for_csv_uploads(self):
        upload = Mock()
        upload.file.name = "prepared-epre.csv"

        dataset, upload_format = load_tablib_dataset(
            upload,
            b"Government,VoteNumber\r\nEastern Cape,6\r\n",
        )

        self.assertEqual(upload_format, "CSV")
        self.assertEqual(dataset.headers, ["Government", "VoteNumber"])
        self.assertEqual(dataset[0], ("Eastern Cape", "6"))

    def test_safe_bulk_create_batch_size_caps_batches_for_sql_server(self):
        self.assertEqual(safe_bulk_create_batch_size(18), 111)
        self.assertEqual(safe_bulk_create_batch_size(16), 125)
        self.assertEqual(safe_bulk_create_batch_size(1), 2000)

    def test_rejects_epre_headers_for_budget_vs_actual_upload(self):
        dataset = Dataset(headers=EPRE_HEADERS)
        dataset.append(
            [
                "Eastern Cape",
                6,
                "Education",
                1,
                "Administration",
                1,
                "Office of the MEC",
                "Current payments",
                "Current payments",
                "Compensation of employees",
                "Salaries and wages",
                "Salaries and wages",
                "Learning and culture",
                "Learning and culture",
                2026,
                2026,
                "Main appropriation",
                10072000,
            ]
        )

        with self.assertRaisesMessage(
            ValueError,
            "Invalid upload columns for Budget-vs-Actual-Provincial",
        ):
            preprocess(
                dataset,
                BUDGET_ACTUAL_HEADERS,
                "Budget-vs-Actual-Provincial",
            )

    def test_maps_valid_rows_to_expected_headers(self):
        dataset = Dataset(headers=BUDGET_ACTUAL_HEADERS)
        dataset.append(
            [
                "Eastern Cape",
                6,
                "Education",
                1,
                "Administration",
                1,
                "Office of the MEC",
                "Current payments",
                "Current payments",
                "Compensation of employees",
                "Salaries and wages",
                "Salaries and wages",
                "Learning and culture",
                2026,
                "Main appropriation",
                "Adjusted appropriation",
                10072000,
            ]
        )

        rows = preprocess(
            dataset,
            BUDGET_ACTUAL_HEADERS,
            "Budget-vs-Actual-Provincial",
        )

        self.assertEqual(rows[0]["BudgetPhase"], "Main appropriation")
        self.assertEqual(rows[0]["AmountKind"], "Adjusted appropriation")
        self.assertEqual(rows[0]["Value"], 10072000)

    def test_budget_vs_actual_national_config_maps_all_headers(self):
        dataset_upload = Mock()
        dataset_upload.id = 1
        dataset_upload.type = "Budget-vs-Actual-National"
        dataset_upload.financialYear.slug = "2026-27"
        dataset_upload.file.read.return_value = b""

        dataset = Dataset(headers=BUDGET_ACTUAL_HEADERS)
        dataset.append(
            [
                "National",
                1,
                "Agriculture",
                1,
                "Administration",
                1,
                "Office of the Director-General",
                "Current payments",
                "Compensation of employees",
                "Salaries and wages",
                "Level 4",
                "Level 5",
                "Executive and administration",
                2026,
                2026,
                "Main appropriation",
                "Total",
                10072000,
            ]
        )

        with patch("budgetportal.dataset_uploading.dataset_preprocessor.DatasetUpload.objects.get", return_value=dataset_upload), \
             patch("budgetportal.dataset_uploading.dataset_preprocessor.load_tablib_dataset", return_value=(dataset, "CSV")), \
             patch("budgetportal.dataset_uploading.dataset_preprocessor.preprocess", return_value=[dict(zip(BUDGET_ACTUAL_HEADERS, dataset[0]))]), \
             patch("budgetportal.dataset_uploading.dataset_preprocessor.Organisation.objects.get"), \
             patch("budgetportal.dataset_uploading.dataset_preprocessor.Sphere.objects.get"), \
             patch("budgetportal.dataset_uploading.dataset_preprocessor.DatasetCategory.objects.get"), \
             patch("budgetportal.dataset_uploading.dataset_preprocessor.Dataset.objects.update_or_create", return_value=(Mock(), True)), \
             patch("budgetportal.dataset_uploading.dataset_preprocessor.DatasetResource.objects.filter"), \
             patch("budgetportal.dataset_uploading.dataset_preprocessor.safe_bulk_create_batch_size", return_value=1000), \
             patch("budgetportal.dataset_uploading.dataset_preprocessor.BudgetVSActualNationalData.objects.filter") as mock_filter, \
             patch("budgetportal.dataset_uploading.dataset_preprocessor.BudgetVSActualNationalData.objects.bulk_create") as mock_bulk_create:
            mock_filter.return_value.delete.return_value = (0, {})

            import_dataset(1)

            created_objects = mock_bulk_create.call_args[0][0]
            self.assertEqual(len(created_objects), 1)
            self.assertEqual(created_objects[0].budgetYear, 2026)
            self.assertEqual(created_objects[0].financialYear, 2026)
            self.assertEqual(created_objects[0].value, 10072000)


class DatasetCategoryResolutionTest(TestCase):
    def test_uses_alternate_existing_category_title(self):
        existing = DatasetCategory.objects.create(
            title="Budgeted and Actual National Expenditure",
            description="Existing category",
        )

        resolved = get_or_create_dataset_category(
            "Budgeted vs Actual National Expenditure",
            description="Expected category",
            alternate_titles=["Budgeted and Actual National Expenditure"],
        )

        self.assertEqual(resolved.id, existing.id)

    def test_creates_missing_category(self):
        resolved = get_or_create_dataset_category(
            "Budgeted vs Actual National Expenditure",
            description="Expected category",
            category_type="Original Budget",
        )

        self.assertEqual(resolved.title, "Budgeted vs Actual National Expenditure")
        self.assertEqual(resolved.description, "Expected category")
        self.assertEqual(resolved.type, "Original Budget")
