from io import BytesIO

import requests
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from mock import Mock, patch
from openpyxl import Workbook

from budgetportal import models as budgetportal_models
from budgetportal.dataset_uploading.dataset_preprocessor import (
    BUDGET_ACTUAL_HEADERS,
    EPRE_HEADERS,
)

from .models import DatasetImportJob, DatasetPreparationJob
from .services import (
    download_source_file,
    find_header_row,
    iter_sheet_records,
    load_rows_from_excel,
    transform_records,
)
from .tasks import run_dataset_import_job, run_dataset_preparation_job


def build_source_workbook():
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Data"
    worksheet.append(["Report title"])
    worksheet.append(
        [
            "Province",
            "Vote No.",
            "Department",
            "Programme No.",
            "Programme",
            "Subprogramme No.",
            "Subprogramme",
            "Econ1",
            "Econ2",
            "Econ3",
            "Econ4",
            "Econ5",
            "Function group",
            "Function group 2",
            "2026/27 Revised baseline",
            "2026/27 Adjusted appropriation",
        ]
    )
    worksheet.append(
        [
            "KwaZulu-Natal",
            "Vote 6",
            "education",
            1,
            "Administration",
            1,
            "Office of the MEC",
            "Current payments",
            "Compensation of employees",
            "Salaries and wages",
            "Level 4",
            "Level 5",
            "Learning and culture",
            "Basic education",
            10,
            20,
        ]
    )
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


class DatasetPreparationServiceTest(SimpleTestCase):
    @patch("dataset_preparation.services.time.sleep")
    @patch("dataset_preparation.services.requests.get")
    def test_download_source_file_retries_transient_request_failures(
        self, mock_get, mock_sleep
    ):
        mock_response = Mock()
        mock_response.content = b"file-bytes"
        mock_response.raise_for_status = Mock()
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("temporary dns failure"),
            mock_response,
        ]

        content = download_source_file("https://example.com/epre.xlsx")

        self.assertEqual(content, b"file-bytes")
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("dataset_preparation.services.time.sleep")
    @patch("dataset_preparation.services.requests.get")
    def test_download_source_file_raises_after_retry_limit(self, mock_get, mock_sleep):
        mock_get.side_effect = requests.exceptions.ConnectionError(
            "temporary dns failure"
        )

        with self.assertRaises(requests.exceptions.ConnectionError):
            download_source_file("https://example.com/epre.xlsx")

        self.assertEqual(mock_get.call_count, 4)
        self.assertEqual(mock_sleep.call_count, 3)

    def test_transforms_epre_rows_into_expected_schema(self):
        workbook_bytes = build_source_workbook()
        rows = load_rows_from_excel(workbook_bytes, "Data")
        header_row_index = find_header_row(rows)
        records = list(iter_sheet_records(rows, header_row_index))

        financial_year = Mock(slug="2026-27")
        transformed_rows = transform_records(
            records,
            financial_year,
            DatasetPreparationJob.DATASET_TYPE_EPRE,
        )

        self.assertEqual(list(transformed_rows[0].keys()), EPRE_HEADERS)
        self.assertEqual(transformed_rows[0]["Government"], "KwaZulu-Natal")
        self.assertEqual(transformed_rows[0]["VoteNumber"], 6)
        self.assertEqual(transformed_rows[0]["BudgetPhase"], "Main appropriation")
        self.assertEqual(transformed_rows[0]["Value"], 10000)

    def test_transforms_budget_vs_actual_rows_into_expected_schema(self):
        workbook_bytes = build_source_workbook()
        rows = load_rows_from_excel(workbook_bytes, "Data")
        header_row_index = find_header_row(rows)
        records = list(iter_sheet_records(rows, header_row_index))

        financial_year = Mock(slug="2026-27")
        transformed_rows = transform_records(
            records,
            financial_year,
            "Budget-vs-Actual-Provincial",
        )

        adjusted_row = [
            row for row in transformed_rows
            if row["BudgetPhase"] == "Adjusted appropriation"
        ][0]

        self.assertEqual(list(adjusted_row.keys()), BUDGET_ACTUAL_HEADERS)
        self.assertEqual(adjusted_row["AmountKind"], "Total")
        self.assertEqual(adjusted_row["Value"], 20000)


class DatasetPreparationJobTest(TestCase):
    @patch("dataset_preparation.tasks.async_task")
    @patch("dataset_preparation.services.requests.get")
    def test_job_prepares_files_and_queues_import_jobs(self, mock_get, mock_async_task):
        user = User.objects.create_user(username="admin", password="password")
        financial_year = budgetportal_models.FinancialYear.objects.create(
            slug="2026-27", published=True
        )
        budgetportal_models.Sphere.objects.create(
            name="Provincial", financial_year=financial_year
        )
        budgetportal_models.Organisation.objects.create(title="National Treasury")
        budgetportal_models.DatasetCategory.objects.create(
            title="Estimates of Provincial Revenue and Expenditure",
            description="EPRE",
        )

        mock_response = Mock()
        mock_response.content = build_source_workbook()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        mock_async_task.side_effect = ["epre-task", "bva-task"]

        job = DatasetPreparationJob.objects.create(
            user=user,
            source_url="https://example.com/epre.xlsx",
            dataset_type=DatasetPreparationJob.DATASET_TYPE_EPRE,
            financial_year=financial_year,
            sheet_name="Data",
        )

        budgetportal_models.DatasetCategory.objects.create(
            title="Budgeted and Actual Provincial Expenditure",
            description="Budget vs actual provincial",
        )

        result = run_dataset_preparation_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, DatasetPreparationJob.STATUS_PREPARED)
        self.assertTrue(job.prepared_file.name.endswith(".csv"))
        self.assertTrue(job.budget_vs_actual_file.name.endswith(".csv"))
        self.assertEqual(
            job.excel_conversion_status,
            DatasetPreparationJob.CONVERSION_STATUS_PENDING,
        )
        self.assertEqual(result["epre_prepared_rows"], 1)
        self.assertEqual(result["budget_vs_actual_prepared_rows"], 1)
        self.assertEqual(job.import_jobs.count(), 2)
        self.assertEqual(
            set(job.import_jobs.values_list("status", flat=True)),
            {DatasetImportJob.STATUS_QUEUED},
        )
        self.assertEqual(
            set(job.import_jobs.values_list("task_id", flat=True)),
            {"epre-task", "bva-task"},
        )

    @patch("dataset_preparation.tasks.async_task")
    @patch("dataset_preparation.services.requests.get")
    def test_import_job_runs_separately_after_preparation(
        self, mock_get, mock_async_task
    ):
        user = User.objects.create_user(username="admin", password="password")
        financial_year = budgetportal_models.FinancialYear.objects.create(
            slug="2026-27", published=True
        )
        budgetportal_models.Sphere.objects.create(
            name="Provincial", financial_year=financial_year
        )
        budgetportal_models.Organisation.objects.create(title="National Treasury")
        budgetportal_models.DatasetCategory.objects.create(
            title="Estimates of Provincial Revenue and Expenditure",
            description="EPRE",
        )
        budgetportal_models.DatasetCategory.objects.create(
            title="Budgeted and Actual Provincial Expenditure",
            description="Budget vs actual provincial",
        )

        mock_response = Mock()
        mock_response.content = build_source_workbook()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        mock_async_task.side_effect = ["epre-task", "bva-task"]

        job = DatasetPreparationJob.objects.create(
            user=user,
            source_url="https://example.com/epre.xlsx",
            dataset_type=DatasetPreparationJob.DATASET_TYPE_EPRE,
            financial_year=financial_year,
            sheet_name="Data",
        )
        run_dataset_preparation_job(job.id)

        import_job = DatasetImportJob.objects.get(
            preparation_job=job,
            dataset_type=DatasetImportJob.DATASET_TYPE_EPRE,
        )
        result = run_dataset_import_job(import_job.id)

        import_job.refresh_from_db()
        self.assertEqual(import_job.status, DatasetImportJob.STATUS_COMPLETED)
        upload = budgetportal_models.DatasetUpload.objects.get(
            id=result["dataset_upload_id"]
        )
        self.assertEqual(upload.user, user)
        dataset = budgetportal_models.Dataset.objects.get(id=result["dataset_id"])
        self.assertEqual(
            dataset.title,
            "Estimates of Provincial Revenue and Expenditure 2026-27",
        )
