"""Safe, database-free parsing helpers for Division of Revenue workbooks."""

import re
from io import BytesIO
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException


SCHEDULE_NUMBERS = (1, 2, 3)
HEADER_SCAN_ROWS = 100
HEADER_TERMS = (
    "province",
    "municipality",
    "allocation",
    "equitable share",
    "vote",
    "sphere",
    "amount",
    "total",
    "category",
    "financial year",
)
YEAR_PATTERN = re.compile(r"\b((?:19|20)\d{2})\s*[-/]\s*(\d{2}|(?:19|20)\d{2})\b")
SCHEDULE_PATTERN = re.compile(
    r"^schedule\s*[_-]?\s*([123])(?:\s*\(\s*\d+\s*\))?\s*$", re.IGNORECASE
)


class WorkbookValidationError(Exception):
    """An uploaded file could not safely be treated as an Excel workbook."""


def normalize_sheet_name(name):
    """Return a comparison-safe representation of a worksheet name."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def find_schedule_sheets(sheet_names):
    """Find exact Schedule 1--3 variants without guessing ambiguous matches."""
    schedules = {number: [] for number in SCHEDULE_NUMBERS}
    for name in sheet_names:
        raw_name = str(name).strip()
        normalised_name = normalize_sheet_name(raw_name)
        # Official DOR workbooks commonly combine these two schedules in one sheet.
        if normalised_name in ("schedule12", "schedule1and2"):
            schedules[1].append(name)
            schedules[2].append(name)
            continue
        match = SCHEDULE_PATTERN.match(raw_name)
        if not match:
            # Normalisation handles whitespace and separator variations while
            # the exact pattern above retains support for "Schedule 1 (1)".
            match = re.match(r"^schedule([123])$", normalised_name)
        if match:
            schedules[int(match.group(1))].append(name)
    return schedules


def _display_value(value):
    """Use simple values in templates and previews, including date-like cells."""
    if value is None:
        return ""
    return str(value).strip()


def _is_blank(row):
    return not any(_display_value(cell.value) for cell in row)


def score_header_row(row):
    """Score a possible table header using general DOR terminology, not a schema."""
    populated_cells = [cell for cell in row if _display_value(cell.value)]
    populated = [_display_value(cell.value) for cell in populated_cells]
    if len(populated) < 2:
        return 0

    text_values = [
        _display_value(cell.value)
        for cell in populated_cells
        if isinstance(cell.value, str)
    ]
    joined = " ".join(value.lower() for value in text_values)
    terminology_hits = sum(term in joined for term in HEADER_TERMS)
    text_ratio = float(len(text_values)) / len(populated)
    return (len(populated) * 3) + int(text_ratio * 5) + (terminology_hits * 5)


def find_header_row(worksheet):
    """Return the best header row near the beginning of a worksheet, if clear."""
    best_row_number = None
    best_score = 0
    upper_bound = min(worksheet.max_row or 0, HEADER_SCAN_ROWS)
    for row_number, row in enumerate(
        worksheet.iter_rows(min_row=1, max_row=upper_bound), start=1
    ):
        score = score_header_row(row)
        if score > best_score:
            best_row_number = row_number
            best_score = score

    # Two populated labels earn 11 points; lower scores are usually title rows.
    if best_score < 11:
        return None
    return best_row_number


def preview_schedule(worksheet):
    """Build a bounded, presentation-ready preview for one detected schedule."""
    result = {
        "sheet_name": worksheet.title,
        "dimensions": worksheet.calculate_dimension(),
        "header_row": None,
        "columns": [],
        "rows": [],
        "meaningful_row_count": 0,
        "warnings": [],
    }
    header_row_number = find_header_row(worksheet)
    if not header_row_number:
        result["warnings"].append("No obvious table header was detected.")
        return result

    result["header_row"] = header_row_number
    header_cells = next(
        worksheet.iter_rows(min_row=header_row_number, max_row=header_row_number)
    )
    columns = [_display_value(cell.value) for cell in header_cells]
    result["columns"] = columns

    for row in worksheet.iter_rows(min_row=header_row_number + 1):
        if _is_blank(row):
            continue
        result["meaningful_row_count"] += 1
        if len(result["rows"]) < 10:
            result["rows"].append([_display_value(cell.value) for cell in row])
    return result


def _normalise_financial_year(start, end):
    end_year = int(end) if len(end) == 4 else (int(start) // 100 * 100) + int(end)
    if end_year != int(start) + 1:
        return None
    return "%s-%02d" % (start, end_year % 100)


def detect_financial_year(workbook):
    """Detect one unambiguous financial year from headings near each sheet's top."""
    years = set()
    for worksheet in workbook.worksheets:
        max_row = min(worksheet.max_row or 0, HEADER_SCAN_ROWS)
        max_col = min(worksheet.max_column or 0, 30)
        for row in worksheet.iter_rows(min_row=1, max_row=max_row, max_col=max_col):
            for cell in row:
                for match in YEAR_PATTERN.finditer(_display_value(cell.value)):
                    year = _normalise_financial_year(match.group(1), match.group(2))
                    if year:
                        years.add(year)
    if len(years) == 1:
        return years.pop(), []
    if not years:
        return None, ["Financial year was not detected."]
    return None, ["More than one financial year was detected: %s." % ", ".join(sorted(years))]


def open_uploaded_workbook(uploaded_file):
    """Open an uploaded workbook with features that could execute code disabled."""
    try:
        uploaded_file.seek(0)
        contents = uploaded_file.read()
        return load_workbook(
            BytesIO(contents), read_only=True, data_only=True, keep_links=False, keep_vba=False
        )
    except (BadZipFile, InvalidFileException, OSError, ValueError, RuntimeError) as error:
        raise WorkbookValidationError(
            "The uploaded file could not be opened as a valid Excel workbook."
        ) from error


def load_and_preview(uploaded_file):
    """Open an untrusted workbook in memory and return a non-persistent preview."""
    workbook = open_uploaded_workbook(uploaded_file)

    try:
        sheet_names = list(workbook.sheetnames)
        matches = find_schedule_sheets(sheet_names)
        financial_year, warnings = detect_financial_year(workbook)
        schedules = {}
        for number, names in matches.items():
            if not names:
                warnings.append("Schedule %s was not found." % number)
                continue
            if len(names) > 1:
                warnings.append(
                    "Schedule %s is ambiguous: %s." % (number, ", ".join(names))
                )
                continue
            schedules[number] = preview_schedule(workbook[names[0]])

        return {
            "filename": uploaded_file.name,
            "file_size": uploaded_file.size,
            "sheet_names": sheet_names,
            "sheet_count": len(sheet_names),
            "financial_year": financial_year,
            "schedules": schedules,
            "warnings": warnings,
            "errors": [],
            "status": "SUCCESS",
        }
    finally:
        workbook.close()
