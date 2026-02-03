from tablib import Databook
from decimal import Decimal
import json
from operator import itemgetter

from budgetportal.models import ENEData, EPREData
from django.db.models import Sum
from tablib import Databook, Dataset
from decimal import Decimal
from collections import defaultdict


# def get_internal_data(financialYear, department, govt_label):
#     queryset = None

#     # 1. Fetch data based on Government Label
#     if govt_label == "National":
#         queryset = ENEData.objects.filter(
#             financialYear=financialYear,
#             department=department
#         ).values("programme").annotate(total_value=Sum("value"))
#     else:
#         queryset = EPREData.objects.filter(
#             financialYear=financialYear,
#             department=department,
#             government=govt_label,
#             budgetPhase='Main appropriation'
#         ).values("programme").annotate(total_value=Sum("value"))

#     # 2. Process the results into the get_data format
#     programmes = []
#     all_programmes_total = Decimal("0")

#     for item in queryset:
#         # Convert the summed value to Decimal for precision
#         val = Decimal(str(item["total_value"] or 0))
#         all_programmes_total += val

#         programmes.append({
#             'programme': item["programme"],
#             'total': val  # Keep as Decimal for internal calculations
#         })

#     # 3. Construct the final dictionary to match get_data
#     # Convert to float only at the final step if JSON serialization requires it
#     return {
#         'all_programmes_total': float(all_programmes_total/1000000),
#         'programmes': [
#             {**p, 'total': float(p['total'])/1000000} for p in programmes
#         ]
#     }

def get_internal_data(financialYear, document_type):
    """
    Same output shape and key style as get_external_data, so matching is easier.

    ENE returns:
      { department: { "Grand Total": float, "Data": { programme: [ {subprogramme,total}, ...] } } }

    EPRE returns:
      { province: { department: { "Grand Total": float, "Data": { programme: [ {subprogramme,total}, ...] } } } }
    """

    if document_type == "ENE":
        queryset = ENEData.objects.filter(
            financialYear=financialYear
        ).values(
            "department", "programme", "subprogramme"
        ).annotate(
            total_value=Sum("value")
        )

        department_totals = defaultdict(lambda: {
            "grand_total": Decimal("0"),
            "totals": defaultdict(Decimal)
        })

        for item in queryset:
            department = item.get("department") or "Unknown"
            programme = item.get("programme") or "Unknown"
            subprogramme = item.get("subprogramme") or "Unknown"
            val = Decimal(str(item.get("total_value") or 0))

            department_totals[department]["totals"][(
                programme, subprogramme)] += val
            department_totals[department]["grand_total"] += val

        result = {}
        for department, data in department_totals.items():
            programmes = defaultdict(list)

            for (programme, subprogramme), total in data["totals"].items():
                programmes[programme].append({
                    "subprogramme": subprogramme,
                    "total": float(total)
                })

            result[department] = {
                "Grand Total": float(data["grand_total"]),
                "Data": dict(programmes)
            }

        return result

    # EPRE
    queryset = EPREData.objects.filter(
        financialYear=financialYear,
        budgetPhase="Main appropriation"
    ).values(
        "government", "department", "programme", "subprogramme"
    ).annotate(
        total_value=Sum("value")
    )

    province_totals = defaultdict(lambda: defaultdict(lambda: {
        "grand_total": Decimal("0"),
        "totals": defaultdict(Decimal)
    }))

    for item in queryset:
        province = (item.get("government") or "Unknown").strip().upper()
        department = (item.get("department") or "Unknown").strip().upper()
        programme = item.get("programme") or "Unknown"
        subprogramme = item.get("subprogramme") or "Unknown"
        val = Decimal(str(item.get("total_value") or 0))

        province_totals[province][department]["totals"][(
            programme, subprogramme)] += val
        province_totals[province][department]["grand_total"] += val

    result = {}
    for province, departments in province_totals.items():
        province_out = {}

        for department, data in departments.items():
            programmes = defaultdict(list)

            for (programme, subprogramme), total in data["totals"].items():
                programmes[programme].append({
                    "subprogramme": subprogramme,
                    "total": float(total)
                })

            province_out[department] = {
                "Grand Total": float(data["grand_total"]),
                "Data": dict(programmes)
            }

        if province_out:
            result[province] = province_out
    return result


def find_col_contains(headers, needle):
    needle = str(needle).strip().lower()
    for i, h in enumerate(headers):
        h = str(h).strip().lower() if h else ""
        if needle in h:
            return i
    raise ValueError(f"Could not find column containing: {needle}")


def year_token(financialYear):
    # supports: 2025, "2025", "2025-26", "2025/26"
    fy = str(financialYear).strip()
    if "/" in fy:
        return fy
    if "-" in fy:
        return fy.replace("-", "/")
    # assume single year like 2025
    y = int(fy)
    return f"{y}/{str(y + 1)[-2:]}"


def get_external_data(file_path, financialYear, document_type):

    year = year_token(financialYear)

    column = "Budget" if document_type == "ENE" else "Revised baseline"
    target_budget_col = f"{year} {column}"

    with open(file_path, "rb") as f:
        book = Databook().load(f, "xlsx")

    sheet = next((s for s in book.sheets() if s.title == "Data"), None)
    if not sheet:
        raise ValueError("Sheet 'Data' not found.")

    rows = list(sheet)

    # 1. Find Header Row
    header_row_idx = None
    for i, row in enumerate(rows):
        row_values = [str(cell).strip()
                      if cell is not None else "" for cell in row]
        if "Programme" in row_values:
            header_row_idx = i
            break

    if header_row_idx is None:
        raise ValueError(
            "Could not find 'Programme' header in sheet. To fix this you need to add an empty row above the current header row. And then re-upload the file."
        )

    headers = [
        str(h).strip() if h is not None else "" for h in rows[header_row_idx]]
    data_rows = rows[header_row_idx + 1:]

    # 2. Identify Column Indices
    try:
        prog_idx = headers.index("Programme")
        subprog_idx = headers.index("Subprogramme")
        dept_idx = headers.index("Department")
        province_idx = headers.index(
            "Province") if document_type == "EPRE" else None

        # budget differs by file. use contains
        budget_idx = find_col_contains(headers, target_budget_col)

    except ValueError as e:
        raise ValueError(f"Missing expected column: {e}")

    # 3. Aggregate
    if document_type == "EPRE":
        department_totals = defaultdict(lambda: defaultdict(lambda: {
            "grand_total": Decimal("0"),
            "totals": defaultdict(Decimal)
        }))
    else:
        department_totals = defaultdict(lambda: {
            "grand_total": Decimal("0"),
            "totals": defaultdict(Decimal)
        })

    for row in data_rows:
        if not row or len(row) <= budget_idx:
            continue

        department = str(row[dept_idx]).strip(
        ) if row[dept_idx] is not None else ""
        if not department:
            continue

        raw_budget = row[budget_idx]
        if raw_budget is None:
            continue

        raw_budget_str = str(raw_budget).strip()
        if raw_budget_str == "":
            continue

        budget_val = Decimal(raw_budget_str.replace(",", ""))
        if budget_val == 0:
            continue

        programme = str(row[prog_idx]).strip(
        ) if row[prog_idx] is not None else "Unknown"
        subprogramme = str(row[subprog_idx]).strip(
        ) if row[subprog_idx] is not None else "Unknown"

        if document_type == "EPRE":
            province = str(row[province_idx]).strip(
            ) if row[province_idx] is not None else ""
            if not province:
                continue
            department_totals[province][department]["totals"][(
                programme, subprogramme)] += budget_val
            department_totals[province][department]["grand_total"] += budget_val
        else:
            department_totals[department]["totals"][(
                programme, subprogramme)] += budget_val
            department_totals[department]["grand_total"] += budget_val

    # 4. Format output
    result = {}

    if document_type == "EPRE":
        for province, departments in department_totals.items():
            province_out = {}

            for department, data in departments.items():
                programmes = defaultdict(list)

                for (programme, subprogramme), total in data["totals"].items():
                    if total == 0:
                        continue
                    programmes[programme].append({
                        "subprogramme": subprogramme,
                        "total": float(total * 1000)
                    })

                if data["grand_total"] == 0:
                    continue

                province_out[department] = {
                    "Grand Total": float(data["grand_total"] * 1000),
                    "Data": dict(programmes)
                }

            if province_out:
                result[province] = province_out

    else:
        for department, data in department_totals.items():
            programmes = defaultdict(list)

            for (programme, subprogramme), total in data["totals"].items():
                if total == 0:
                    continue
                programmes[programme].append({
                    "subprogramme": subprogramme,
                    "total": float(total * 1000)
                })

            if data["grand_total"] == 0:
                continue

            result[department] = {
                "Grand Total": float(data["grand_total"] * 1000),
                "Data": dict(programmes)
            }

    return result
