from django.test import SimpleTestCase
from mock import Mock
from tablib import Dataset

from budgetportal.dataset_uploading import preprocess
from budgetportal.dataset_uploading.dataset_preprocessor import (
    BUDGET_ACTUAL_HEADERS,
    EPRE_HEADERS,
    load_tablib_dataset,
    safe_bulk_create_batch_size,
)


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
