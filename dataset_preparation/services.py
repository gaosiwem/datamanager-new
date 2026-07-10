import os
import re
import time
from csv import DictWriter
from io import BytesIO, StringIO
from urllib.parse import urlparse

import requests
from django.core.files.base import ContentFile
from openpyxl import Workbook, load_workbook

from budgetportal import models as budgetportal_models
from budgetportal.dataset_uploading import check_input_column_order
from budgetportal.dataset_uploading.dataset_preprocessor import (
    BUDGET_ACTUAL_HEADERS,
    EPRE_HEADERS,
)

from .models import DatasetPreparationJob


YEAR_PHASE_REGEX = re.compile(r"^\s*(20\d{2})/\d{2}\s+(.+?)\s*$")

HEADER_ALIASES = {
    "province": "Government",
    "government": "Government",
    "vote no.": "VoteNumber",
    "vote no": "VoteNumber",
    "voteno": "VoteNumber",
    "vote number": "VoteNumber",
    "vote": "VoteNumber",
    "department": "Department",
    "programme no.": "ProgNumber",
    "programme no": "ProgNumber",
    "program no.": "ProgNumber",
    "prognumber": "ProgNumber",
    "programme": "Programme",
    "subprogramme no.": "SubprogNumber",
    "subprogramme no": "SubprogNumber",
    "sub program no.": "SubprogNumber",
    "subprognumber": "SubprogNumber",
    "subprogramme": "Subprogramme",
    "econ1": "EconomicClassification1",
    "econ2": "EconomicClassification2",
    "econ3": "EconomicClassification3",
    "econ4": "EconomicClassification4",
    "econ5": "EconomicClassification5",
    "economicclassification1": "EconomicClassification1",
    "economicclassification2": "EconomicClassification2",
    "economicclassification3": "EconomicClassification3",
    "economicclassification4": "EconomicClassification4",
    "economicclassification5": "EconomicClassification5",
    "function group": "FunctionGroup1",
    "function group 1": "FunctionGroup1",
    "functiongroup1": "FunctionGroup1",
    "function group 2": "FunctionGroup2",
    "functiongroup2": "FunctionGroup2",
}

TITLE_CASE_SMALL_WORDS = {
    "And": "and",
    "Of": "of",
    "The": "the",
}

PHASE_ALIASES = {
    "main appropriation": "Main appropriation",
    "adjusted appropriation": "Adjusted appropriation",
    "baseline": "Baseline",
    "revised baseline": "Revised baseline",
    "revised estimate": "Revised estimate",
    "audited outcome": "Audited outcome",
    "audit outcome": "Audited outcome",
    "audited outcomes": "Audited outcome",
    "preliminary outcome": "Preliminary outcome",
    "final appropriation": "Final appropriation",
}


class DatasetPreparationError(Exception):
    pass


DOWNLOAD_MAX_ATTEMPTS = 4
DOWNLOAD_RETRY_DELAY_SECONDS = 2


def emit_service_progress(message):
    print("[dataset_preparation.services] {}".format(message), flush=True)


def download_source_file(source_url):
    emit_service_progress("Downloading source file from {}".format(source_url))
    last_error = None

    for attempt in range(1, DOWNLOAD_MAX_ATTEMPTS + 1):
        try:
            response = requests.get(source_url, timeout=120)
            response.raise_for_status()
            emit_service_progress(
                "Downloaded {} bytes from {}".format(len(response.content), source_url)
            )
            return response.content
        except requests.exceptions.HTTPError:
            # HTTP errors are not transient DNS issues, so fail fast.
            raise
        except requests.exceptions.RequestException as exc:
            last_error = exc
            if attempt == DOWNLOAD_MAX_ATTEMPTS:
                break
            emit_service_progress(
                "Download attempt {} of {} failed: {}. Retrying in {} seconds.".format(
                    attempt,
                    DOWNLOAD_MAX_ATTEMPTS,
                    exc,
                    DOWNLOAD_RETRY_DELAY_SECONDS,
                )
            )
            time.sleep(DOWNLOAD_RETRY_DELAY_SECONDS)

    raise last_error


def filename_from_url(source_url):
    path = urlparse(source_url).path
    filename = os.path.basename(path)
    return filename or "dataset-source.xlsx"


def save_content_to_field(instance, field_name, filename, content_bytes):
    content_file = ContentFile(content_bytes)
    getattr(instance, field_name).save(filename, content_file, save=False)


def load_rows_from_excel(content_bytes, sheet_name):
    emit_service_progress("Loading workbook sheet '{}'".format(sheet_name))
    workbook = load_workbook(BytesIO(content_bytes), data_only=True, read_only=True)
    target_sheet_name = sheet_name or workbook.sheetnames[0]
    if target_sheet_name not in workbook.sheetnames:
        raise DatasetPreparationError(
            "Could not find sheet '{}' in source workbook.".format(target_sheet_name)
        )
    worksheet = workbook[target_sheet_name]
    rows = [list(row) for row in worksheet.iter_rows(values_only=True)]
    emit_service_progress(
        "Loaded {} rows from sheet '{}'".format(len(rows), target_sheet_name)
    )
    return rows


def normalize_text(value):
    if value is None:
        return ""
    return str(value).strip()


def normalize_key(value):
    return re.sub(r"[^a-z0-9]+", " ", normalize_text(value).lower()).strip()


def normalize_phase_name(value):
    normalized = normalize_key(value)
    return PHASE_ALIASES.get(normalized)


def find_header_row(rows):
    for index, row in enumerate(rows):
        row_values = [normalize_key(value) for value in row]
        if "programme" in row_values:
            emit_service_progress("Found header row at index {}".format(index))
            return index
    raise DatasetPreparationError("Could not find Programme header row in source workbook.")


def build_canonical_headers(header_row):
    headers = []
    for value in header_row:
        text = normalize_text(value)
        canonical = HEADER_ALIASES.get(normalize_key(text), text)
        headers.append(canonical)
    return headers


def iter_sheet_records(rows, header_row_index):
    headers = build_canonical_headers(rows[header_row_index])
    for row in rows[header_row_index + 1 :]:
        if not any(value not in (None, "") for value in row):
            continue
        padded = list(row) + [None] * max(0, len(headers) - len(row))
        yield dict(zip(headers, padded))


def extract_value_columns(headers):
    value_columns = []
    for header in headers:
        if YEAR_PHASE_REGEX.match(normalize_text(header)):
            value_columns.append(header)
    if not value_columns:
        raise DatasetPreparationError(
            "No year/phase columns matched the expected pattern YYYY/YY."
        )
    return value_columns


def coerce_vote_number(value):
    text = normalize_text(value)
    match = re.search(r"(\d+)", text)
    if not match:
        return None
    return int(match.group(1))


def coerce_numeric_value(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return int(round(float(value))) * 1000

    text = normalize_text(value).replace(",", "").replace(" ", "")
    if not text:
        return None
    try:
        return int(round(float(text))) * 1000
    except ValueError:
        return None


def format_title_case(value):
    text = normalize_text(value)
    if not text:
        return ""
    result = text.title()
    for original, replacement in TITLE_CASE_SMALL_WORDS.items():
        result = re.sub(r"\b{}\b".format(original), replacement, result)
    return result.replace("Kwazulu-Natal", "KwaZulu-Natal")


def build_row(record, financial_year, phase_name, value, dataset_type):
    base_row = {
        "Government": format_title_case(record.get("Government")),
        "VoteNumber": coerce_vote_number(record.get("VoteNumber")),
        "Department": format_title_case(record.get("Department")),
        "ProgNumber": record.get("ProgNumber"),
        "Programme": record.get("Programme"),
        "SubprogNumber": record.get("SubprogNumber"),
        "Subprogramme": record.get("Subprogramme"),
        "EconomicClassification1": record.get("EconomicClassification1"),
        "EconomicClassification2": record.get("EconomicClassification2"),
        "EconomicClassification3": record.get("EconomicClassification3"),
        "EconomicClassification4": record.get("EconomicClassification4"),
        "EconomicClassification5": record.get("EconomicClassification5"),
        "FunctionGroup1": record.get("FunctionGroup1"),
        "BudgetYear": financial_year,
        "FinancialYear": financial_year,
        "BudgetPhase": phase_name,
        "Value": value,
    }

    if dataset_type == DatasetPreparationJob.DATASET_TYPE_EPRE:
        base_row["FunctionGroup2"] = record.get("FunctionGroup2")
        ordered_headers = EPRE_HEADERS
    else:
        base_row["AmountKind"] = "Total"
        ordered_headers = BUDGET_ACTUAL_HEADERS

    return {header: base_row.get(header) for header in ordered_headers}


def transform_records(records, target_financial_year, dataset_type):
    records = list(records)
    if not records:
        raise DatasetPreparationError("The source workbook does not contain any data rows.")
    emit_service_progress(
        "Transforming {} records for {} {}".format(
            len(records), dataset_type, target_financial_year.slug
        )
    )

    value_columns = extract_value_columns(records[0].keys())
    target_year = target_financial_year.slug.split("-")[0]

    if dataset_type == DatasetPreparationJob.DATASET_TYPE_EPRE:
        wanted_phases = {
            "Baseline",
            "Revised baseline",
            "Main appropriation",
        }
    elif dataset_type == "Budget-vs-Actual-Provincial":
        wanted_phases = {
            "Adjusted appropriation",
            "Audited outcome",
            "Preliminary outcome",
            "Baseline",
            "Main appropriation",
            "Revised baseline",
            "Revised estimate",
            "Final appropriation",
        }
    else:
        raise DatasetPreparationError(
            "Unsupported preparation type '{}'.".format(dataset_type)
        )

    output_rows = []
    discovered_columns = []
    for record in records:
        for column_name in value_columns:
            match = YEAR_PHASE_REGEX.match(normalize_text(column_name))
            if not match:
                continue
            source_financial_year = match.group(1)
            raw_phase_name = match.group(2).strip()
            phase_name = normalize_phase_name(raw_phase_name)
            discovered_columns.append("{} {}".format(source_financial_year, raw_phase_name))
            if phase_name is None:
                continue
            if phase_name not in wanted_phases:
                continue

            value = coerce_numeric_value(record.get(column_name))
            if value is None:
                continue

            if dataset_type == DatasetPreparationJob.DATASET_TYPE_EPRE:
                if source_financial_year != target_year:
                    continue
                budget_phase = "Main appropriation"
            else:
                budget_phase = phase_name

            output_rows.append(
                build_row(record, source_financial_year, budget_phase, value, dataset_type)
            )

    if not output_rows:
        raise DatasetPreparationError(
            "Preparation completed but no rows matched the expected phases for "
            "{} in financial year {}. Found year/phase columns: {}.".format(
                dataset_type,
                target_financial_year.slug,
                ", ".join(sorted(set(discovered_columns))) or "none",
            )
        )

    emit_service_progress(
        "Transformed {} output rows for {}".format(len(output_rows), dataset_type)
    )
    return output_rows


def write_prepared_csv(rows, headers):
    emit_service_progress("Writing {} rows to CSV".format(len(rows)))
    buffer = StringIO()
    writer = DictWriter(buffer, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        writer.writerow({header: row.get(header) for header in headers})
    return buffer.getvalue().encode("utf-8-sig")


def read_csv_bytes(content_bytes):
    decoded = content_bytes.decode("utf-8-sig")
    rows = decoded.splitlines()
    if not rows:
        raise DatasetPreparationError("Prepared CSV file is empty.")
    import csv

    reader = csv.reader(rows)
    rows = list(reader)
    if not rows:
        raise DatasetPreparationError("Prepared CSV file is empty.")
    return rows[0], rows[1:]


def write_excel_from_csv_bytes(content_bytes):
    headers, data_rows = read_csv_bytes(content_bytes)
    emit_service_progress(
        "Converting CSV to Excel with {} data rows".format(len(data_rows))
    )
    workbook = Workbook(write_only=True)
    worksheet = workbook.create_sheet(title="Prepared Dataset")
    worksheet.append(headers)
    for row in data_rows:
        worksheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def validate_prepared_headers(headers, dataset_type):
    expected_headers = (
        EPRE_HEADERS
        if dataset_type == DatasetPreparationJob.DATASET_TYPE_EPRE
        else BUDGET_ACTUAL_HEADERS
    )
    check_input_column_order(headers, expected_headers, dataset_type)


def prepare_dataset_job(job):
    emit_service_progress(
        "Preparing dataset job {} for financial year {}".format(
            job.id, job.financial_year.slug
        )
    )
    source_content = download_source_file(job.source_url)
    raw_filename = filename_from_url(job.source_url)
    save_content_to_field(job, "raw_file", raw_filename, source_content)
    emit_service_progress("Saved raw file as {}".format(raw_filename))

    rows = load_rows_from_excel(source_content, job.sheet_name)
    header_row_index = find_header_row(rows)
    records = list(iter_sheet_records(rows, header_row_index))

    epre_rows = transform_records(
        records,
        job.financial_year,
        DatasetPreparationJob.DATASET_TYPE_EPRE,
    )
    validate_prepared_headers(list(epre_rows[0].keys()), DatasetPreparationJob.DATASET_TYPE_EPRE)
    epre_bytes = write_prepared_csv(
        epre_rows,
        list(epre_rows[0].keys()),
    )
    save_content_to_field(
        job,
        "prepared_file",
        "prepared-{}-{}.csv".format(
            DatasetPreparationJob.DATASET_TYPE_EPRE.lower(),
            job.financial_year.slug,
        ),
        epre_bytes,
    )
    emit_service_progress(
        "Saved EPRE prepared file with {} rows".format(len(epre_rows))
    )

    budget_vs_actual_rows = transform_records(
        records,
        job.financial_year,
        "Budget-vs-Actual-Provincial",
    )
    validate_prepared_headers(
        list(budget_vs_actual_rows[0].keys()),
        "Budget-vs-Actual-Provincial",
    )
    budget_vs_actual_bytes = write_prepared_csv(
        budget_vs_actual_rows,
        list(budget_vs_actual_rows[0].keys()),
    )
    save_content_to_field(
        job,
        "budget_vs_actual_file",
        "prepared-{}-{}.csv".format(
            "budget-vs-actual-provincial",
            job.financial_year.slug,
        ),
        budget_vs_actual_bytes,
    )
    emit_service_progress(
        "Saved Budget vs Actual prepared file with {} rows".format(
            len(budget_vs_actual_rows)
        )
    )

    return {
        "EPRE": epre_rows,
        "Budget-vs-Actual-Provincial": budget_vs_actual_rows,
    }


def create_dataset_upload_from_field(job, field_name, dataset_type):
    prepared_field = getattr(job, field_name)
    if not prepared_field:
        raise DatasetPreparationError(
            "Prepared file '{}' is missing for this job.".format(field_name)
        )

    upload = budgetportal_models.DatasetUpload(
        user=job.user,
        type=dataset_type,
        financialYear=job.financial_year,
    )
    prepared_field.open("rb")
    upload.file.save(
        os.path.basename(prepared_field.name),
        ContentFile(prepared_field.read()),
        save=False,
    )
    prepared_field.close()
    upload.save()
    return upload


def convert_prepared_csvs_to_excel(job):
    conversions = [
        ("prepared_file", "prepared_excel_file"),
        ("budget_vs_actual_file", "budget_vs_actual_excel_file"),
    ]
    for source_field_name, target_field_name in conversions:
        source_field = getattr(job, source_field_name)
        if not source_field:
            raise DatasetPreparationError(
                "Prepared CSV '{}' is missing for this job.".format(source_field_name)
            )
        emit_service_progress(
            "Converting {} for job {}".format(source_field.name, job.id)
        )
        source_field.open("rb")
        excel_bytes = write_excel_from_csv_bytes(source_field.read())
        source_field.close()
        target_name = os.path.splitext(os.path.basename(source_field.name))[0] + ".xlsx"
        save_content_to_field(job, target_field_name, target_name, excel_bytes)
        emit_service_progress("Saved Excel copy as {}".format(target_name))
