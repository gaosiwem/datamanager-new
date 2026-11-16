"""Import the official Schedule 1--3 equitable-share tables into domain models."""

from django.db import connection, transaction
from django.db.models import Max

from budgetportal.models import (
    DivisionOfRevenue,
    DivisionOfRevenueAllocation,
    FinancialYear,
    Government,
    Municipality,
    Sphere,
)

from .parser import WorkbookValidationError, open_uploaded_workbook


SCHEDULE_1_2_SHEET = "Schedule 1 & 2"
SCHEDULE_3_SHEET = "Schedule 3"
PROVINCES_BY_CODE = {
    1: "Eastern Cape", 2: "Free State", 3: "Gauteng", 4: "KwaZulu-Natal",
    5: "Limpopo", 6: "Mpumalanga", 7: "Northern Cape", 8: "North West",
    9: "Western Cape",
}
SQL_SERVER_SAFE_PARAM_LIMIT = 2000


def _year_slug(value):
    text = str(value).strip()
    if len(text) == 7 and text[4] in "-/":
        return "%s-%s" % (text[:4], text[-2:])
    raise WorkbookValidationError("A Schedule heading contains an invalid financial year.")


def _value(worksheet, row, column):
    return worksheet.cell(row=row, column=column).value


def _schedule_years(worksheet, row, first_column):
    years = []
    # The official workbook places labels such as "Forward Estimates" beside
    # the year headings, and splits the final two years across the next row.
    for heading_row in (row, row + 1):
        for column in range(first_column, first_column + 3):
            value = _value(worksheet, heading_row, column)
            try:
                year = _year_slug(value)
            except WorkbookValidationError:
                continue
            if year not in years:
                years.append(year)
    if len(years) != 3:
        raise WorkbookValidationError("Could not read the three allocation years from the workbook.")
    return years


def _bill_financial_year(year_slug):
    try:
        return FinancialYear.objects.get(slug=year_slug)
    except FinancialYear.DoesNotExist:
        raise WorkbookValidationError(
            "Create the %s FinancialYear record before importing." % year_slug
        )


def _create_allocation(bill, schedule_number, source_row, amounts, **recipient):
    return DivisionOfRevenueAllocation(
        division_of_revenue=bill,
        schedule_number=schedule_number,
        source_row_number=source_row,
        amount_rands=int(amounts[0]) * 1000,
        forward_estimate_1_rands=int(amounts[1]) * 1000,
        forward_estimate_2_rands=int(amounts[2]) * 1000,
        **recipient
    )


def _allocation_batch_size():
    """Keep SQL Server bulk inserts below its 2,100-parameter limit."""
    inserted_fields = len(DivisionOfRevenueAllocation._meta.fields) - 1
    return max(1, SQL_SERVER_SAFE_PARAM_LIMIT // inserted_fields)


def import_official_schedules(uploaded_file):
    """Create domain records from the official Schedule 1--3 workbook tables."""
    workbook = open_uploaded_workbook(uploaded_file)
    try:
        if SCHEDULE_1_2_SHEET not in workbook.sheetnames or SCHEDULE_3_SHEET not in workbook.sheetnames:
            raise WorkbookValidationError(
                "This workbook must contain the official 'Schedule 1 & 2' and 'Schedule 3' worksheets."
            )
        schedule_1_2 = workbook[SCHEDULE_1_2_SHEET]
        schedule_3 = workbook[SCHEDULE_3_SHEET]
        year_slugs = _schedule_years(schedule_1_2, 6, 4)
        bill_year = _bill_financial_year(year_slugs[0])

        spheres = {
            sphere.name.lower(): sphere
            for sphere in Sphere.objects.filter(financial_year=bill_year)
        }
        missing_spheres = [name for name in ("national", "provincial") if name not in spheres]
        if missing_spheres:
            raise WorkbookValidationError(
                "Create the %s sphere(s) for %s before importing."
                % (", ".join(missing_spheres), bill_year.slug)
            )

        provincial_governments = {
            government.name.lower(): government
            for government in Government.objects.filter(sphere=spheres["provincial"])
        }
        missing_provinces = [
            name for name in PROVINCES_BY_CODE.values() if name.lower() not in provincial_governments
        ]
        if missing_provinces:
            raise WorkbookValidationError(
                "Create the provincial Government records for %s before importing: %s."
                % (bill_year.slug, ", ".join(missing_provinces))
            )

        with transaction.atomic():
            version = (
                DivisionOfRevenue.objects.filter(financial_year=bill_year).aggregate(Max("version"))["version__max"]
                or 0
            ) + 1
            bill = DivisionOfRevenue.objects.create(
                financial_year=bill_year, version=version, source_filename=uploaded_file.name
            )
            allocations = []

            # Schedule 1: rows 9--11 are National, Provincial and Local; row 12 is a total.
            for row in range(9, 12):
                sphere_name = str(_value(schedule_1_2, row, 3)).replace("1,2", "").strip().lower()
                allocations.append(
                    _create_allocation(
                        bill, 1, row,
                        [_value(schedule_1_2, row, column) for column in range(4, 7)],
                        sphere=spheres.get(sphere_name),
                        schedule_1_recipient=sphere_name,
                    )
                )

            # Schedule 2: provincial allocations; ignore the zero-value Unallocated and total rows.
            for row in range(30, 39):
                province_name = str(_value(schedule_1_2, row, 3)).strip()
                allocations.append(
                    _create_allocation(
                        bill, 2, row,
                        [_value(schedule_1_2, row, column) for column in range(4, 7)],
                        government=provincial_governments[province_name.lower()],
                    )
                )

            municipalities = {}
            municipality_rows = []
            for row in range(12, schedule_3.max_row + 1):
                code = _value(schedule_3, row, 4)
                name = _value(schedule_3, row, 5)
                if not code or not name:
                    continue
                province_code = _value(schedule_3, row, 15)
                category = _value(schedule_3, row, 3)
                if province_code not in PROVINCES_BY_CODE or category not in ("A", "B", "C"):
                    raise WorkbookValidationError("Schedule 3 contains an invalid municipality identifier.")
                municipalities[str(code)] = {
                    "name": str(name).strip(),
                    "category": category,
                    "province": provincial_governments[PROVINCES_BY_CODE[province_code].lower()],
                }
                municipality_rows.append((row, str(code)))

            existing = {
                municipality.code: municipality
                for municipality in Municipality.objects.filter(code__in=municipalities)
            }
            for code, details in municipalities.items():
                municipality, _ = Municipality.objects.get_or_create(code=code, defaults=details)
                if municipality.pk not in [item.pk for item in existing.values()]:
                    existing[code] = municipality

            for row, code in municipality_rows:
                allocations.append(
                    _create_allocation(
                        bill, 3, row,
                        [_value(schedule_3, row, column) for column in range(6, 9)],
                        municipality=existing[code],
                    )
                )
            DivisionOfRevenueAllocation.objects.bulk_create(
                allocations, batch_size=_allocation_batch_size()
            )
    finally:
        workbook.close()
    return bill


def repair_schedule_3_municipalities(bill, uploaded_file):
    """Link legacy Schedule 3 allocations to the municipalities in their workbook.

    Earlier imports retained the Schedule 3 source row but did not persist its
    municipality foreign key.  Repairing the relationship is safe: it neither
    changes the allocation amounts nor creates a new bill version.
    """
    workbook = open_uploaded_workbook(uploaded_file)
    try:
        if SCHEDULE_3_SHEET not in workbook.sheetnames:
            raise WorkbookValidationError(
                "This workbook must contain the official 'Schedule 3' worksheet."
            )
        schedule_3 = workbook[SCHEDULE_3_SHEET]
        codes_by_row = {
            row: str(_value(schedule_3, row, 4))
            for row in range(12, schedule_3.max_row + 1)
            if _value(schedule_3, row, 4) and _value(schedule_3, row, 5)
        }
        municipalities = {
            municipality.code: municipality
            for municipality in Municipality.objects.filter(code__in=codes_by_row.values())
        }
        allocations = list(
            bill.allocations.filter(schedule_number=3, municipality__isnull=True)
        )
        rows_to_repair = [
            (allocation.source_row_number, municipalities.get(codes_by_row.get(allocation.source_row_number)).pk)
            for allocation in allocations
            if municipalities.get(codes_by_row.get(allocation.source_row_number)) is not None
        ]
        if not rows_to_repair:
            return 0

        # django-mssql generates invalid SQL for QuerySet.bulk_update(). A
        # single parameterised CASE update is compatible with SQL Server and
        # remains well below its 2,100-parameter limit (258 x 2 parameters).
        table = DivisionOfRevenueAllocation._meta.db_table
        case_sql = " ".join("WHEN %s THEN %s" for _row, _municipality in rows_to_repair)
        parameters = [
            value
            for row, municipality_id in rows_to_repair
            for value in (row, municipality_id)
        ]
        parameters.extend((bill.pk,))
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE [{table}] "
                "SET [municipality_id] = CASE [source_row_number] {case_sql} END "
                "WHERE [division_of_revenue_id] = %s "
                "AND [schedule_number] = 3 AND [municipality_id] IS NULL".format(
                    table=table, case_sql=case_sql
                ),
                parameters,
            )
        return len(rows_to_repair)
    finally:
        workbook.close()
