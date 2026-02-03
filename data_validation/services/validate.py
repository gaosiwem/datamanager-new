import json
from decimal import Decimal
from data_validation.models import ValidationResult
from django.db import transaction

from data_validation.services.extract_data import get_internal_data

# def run_validation(validation_run, external_data):#     try:
#         # 1. Get internal data (now returns a dict, not a JSON string)
#         internal_data = get_internal_data(
#             financialYear=validation_run.financial_year,
#             department=validation_run.department,
#             govt_label="National",
#         )

#         # 2. Map the internal programmes to a dictionary for easy lookup
#         # Updated key from 'children' to 'programmes' to match your latest structure
#         internal_totals_map = {
#             p["programme"]: Decimal(str(p["total"]))
#             for p in internal_data["programmes"]
#         }

#         external_data_map = {
#             p["programme"]: Decimal(str(p["total"]))
#             for p in external_data["programmes"]
#         }

#         # 3. Create a set of all unique programme names across both sources
#         # 'external_data' should be a dict of {name: value}
#         all_programmes = set(internal_totals_map.keys()
#                              ) | set(external_data_map.keys())
        
#         for programme in all_programmes:
#             # Skip metadata keys if they were accidentally passed in the dict
#             if programme in ["Direct charge against the National Revenue Fund", "programmes"]:
#                 continue

#             # 4. Extract values and ensure they are Decimals
#             # This prevents the "unsupported operand type for -: 'Decimal' and 'float'" error
#             internal_val = internal_totals_map.get(programme, Decimal("0"))

#             external_val = external_data_map.get(programme, Decimal("0"))

#             delta = internal_val - external_val

#             # 5. Save the validation result to the database
#             ValidationResult.objects.create(
#                 validation_run=validation_run,
#                 programme=programme,
#                 internal_amount=internal_val,
#                 external_amount=external_val,
#                 is_valid=abs(delta) < Decimal("0.01"),
#             )

#         print(f"Validation completed for {validation_run.department}")

#     except Exception as e:
#         print("Validation error:", str(e))

from decimal import Decimal
from django.db import transaction


def run_validation(validation_run, external_data):
    """
    Compares Internal vs External data at:
    - Department level (Grand Total)
    - Programme level
    - Subprogramme level

    Works for both EPRE and ENE.
    Removes duplicates by normalising Programme/Subprogramme keys (case, spacing).
    Includes configurable tolerance.
    """

    def norm_key(s):
        return " ".join(str(s).strip().lower().split()) if s is not None else ""

    def build_name_map(d):
        return {norm_key(name): name for name in d.keys()}

    def build_sub_map(subs):
        return {norm_key(s["subprogramme"]): Decimal(str(s["total"])) for s in subs}

    def pick_label_from_subs(subs, nkey, fallback):
        for s in subs:
            if norm_key(s["subprogramme"]) == nkey:
                return s["subprogramme"]
        return fallback

    def is_close(a, b, tol):
        return abs(a - b) <= tol

    try:
        with transaction.atomic():

            # tolerance (adjust here)
            # If your values are in rands, Decimal("1") means R1 tolerance.
            # If they are in thousands, adjust accordingly.

            tolerance = Decimal("1000")
            internal_data = get_internal_data(
                financialYear=str(
                    validation_run.financial_year.slug).split("-")[0],
                document_type=validation_run.document_type,
            )

            ValidationResult.objects.filter(
                validation_run=validation_run
            ).delete()

            if validation_run.document_type == "EPRE":
                # EPRE: province -> department -> ...
                
                all_provinces = set(internal_data.keys()) | set(
                    external_data.keys())

                for province in all_provinces:
                    internal_departments = internal_data.get(
                        province, {}) or {}
                    external_departments = external_data.get(
                        province, {}) or {}

                    all_departments = set(internal_departments.keys()) | set(
                        external_departments.keys())

                    for department in all_departments:
                        internal_dept = internal_departments.get(
                            department, {}) or {}
                        external_dept = external_departments.get(
                            department, {}) or {}

                        internal_grand = Decimal(
                            str(internal_dept.get("Grand Total", 0) or 0))
                        external_grand = Decimal(
                            str(external_dept.get("Grand Total", 0) or 0))

                        ValidationResult.objects.create(
                            validation_run=validation_run,
                            province=province,
                            department=department,
                            programme="All Programmes",
                            subprogramme="All Subprogrammes",
                            level="DEPARTMENT",
                            internal_amount=internal_grand,
                            external_amount=external_grand,
                            is_valid=is_close(
                                internal_grand, external_grand, tolerance),
                        )

                        internal_programmes = internal_dept.get(
                            "Data", {}) or {}
                        external_programmes = external_dept.get(
                            "Data", {}) or {}

                        # FIX: normalise programme names to avoid duplicates
                        internal_prog_map = build_name_map(internal_programmes)
                        external_prog_map = build_name_map(external_programmes)
                        all_prog_norm = set(internal_prog_map.keys()) | set(
                            external_prog_map.keys())

                        for prog_norm in all_prog_norm:
                            internal_prog_name = internal_prog_map.get(
                                prog_norm)
                            external_prog_name = external_prog_map.get(
                                prog_norm)

                            internal_subs = internal_programmes.get(
                                internal_prog_name, []) if internal_prog_name else []
                            external_subs = external_programmes.get(
                                external_prog_name, []) if external_prog_name else []

                            programme_label = internal_prog_name or external_prog_name or prog_norm

                            internal_prog_total = sum(
                                Decimal(str(s["total"])) for s in internal_subs)
                            external_prog_total = sum(
                                Decimal(str(s["total"])) for s in external_subs)

                            ValidationResult.objects.create(
                                validation_run=validation_run,
                                province=province,
                                department=department,
                                programme=programme_label,
                                subprogramme="All Subprogrammes",
                                level="PROGRAMME",
                                internal_amount=internal_prog_total,
                                external_amount=external_prog_total,
                                is_valid=is_close(
                                    internal_prog_total, external_prog_total, tolerance),
                            )

                            # FIX: normalise subprogramme names to avoid duplicates
                            internal_sub_map = build_sub_map(internal_subs)
                            external_sub_map = build_sub_map(external_subs)
                            all_sub_norm = set(internal_sub_map.keys()) | set(
                                external_sub_map.keys())

                            for sub_norm in all_sub_norm:
                                internal_val = internal_sub_map.get(
                                    sub_norm, Decimal("0"))
                                external_val = external_sub_map.get(
                                    sub_norm, Decimal("0"))

                                subprogramme_label = pick_label_from_subs(
                                    internal_subs, sub_norm, None)
                                if subprogramme_label is None:
                                    subprogramme_label = pick_label_from_subs(
                                        external_subs, sub_norm, sub_norm)

                                ValidationResult.objects.create(
                                    validation_run=validation_run,
                                    province=province,
                                    department=department,
                                    programme=programme_label,
                                    subprogramme=subprogramme_label,
                                    level="SUBPROGRAMME",
                                    internal_amount=internal_val,
                                    external_amount=external_val,
                                    is_valid=is_close(
                                        internal_val, external_val, tolerance),
                                )

            else:
                # ENE: department -> ...
                all_departments = set(internal_data.keys()) | set(
                    external_data.keys())

                for department in all_departments:
                    internal_dept = internal_data.get(department, {}) or {}
                    external_dept = external_data.get(department, {}) or {}

                    internal_grand = Decimal(
                        str(internal_dept.get("Grand Total", 0) or 0))
                    external_grand = Decimal(
                        str(external_dept.get("Grand Total", 0) or 0))

                    ValidationResult.objects.create(
                        validation_run=validation_run,
                        province="NATIONAL",
                        department=department,
                        programme="All Programmes",
                        subprogramme="All Subprogrammes",
                        level="DEPARTMENT",
                        internal_amount=internal_grand,
                        external_amount=external_grand,
                        is_valid=is_close(
                            internal_grand, external_grand, tolerance),
                    )

                    internal_programmes = internal_dept.get("Data", {}) or {}
                    external_programmes = external_dept.get("Data", {}) or {}

                    # FIX: normalise programme names to avoid duplicates
                    internal_prog_map = build_name_map(internal_programmes)
                    external_prog_map = build_name_map(external_programmes)
                    all_prog_norm = set(internal_prog_map.keys()) | set(
                        external_prog_map.keys())

                    for prog_norm in all_prog_norm:
                        internal_prog_name = internal_prog_map.get(prog_norm)
                        external_prog_name = external_prog_map.get(prog_norm)

                        internal_subs = internal_programmes.get(
                            internal_prog_name, []) if internal_prog_name else []
                        external_subs = external_programmes.get(
                            external_prog_name, []) if external_prog_name else []

                        programme_label = internal_prog_name or external_prog_name or prog_norm

                        internal_prog_total = sum(
                            Decimal(str(s["total"])) for s in internal_subs)
                        external_prog_total = sum(
                            Decimal(str(s["total"])) for s in external_subs)

                        ValidationResult.objects.create(
                            validation_run=validation_run,
                            province="NATIONAL",
                            department=department,
                            programme=programme_label,
                            subprogramme="All Subprogrammes",
                            level="PROGRAMME",
                            internal_amount=internal_prog_total,
                            external_amount=external_prog_total,
                            is_valid=is_close(
                                internal_prog_total, external_prog_total, tolerance),
                        )

                        # FIX: normalise subprogramme names to avoid duplicates
                        internal_sub_map = build_sub_map(internal_subs)
                        external_sub_map = build_sub_map(external_subs)
                        all_sub_norm = set(internal_sub_map.keys()) | set(
                            external_sub_map.keys())

                        for sub_norm in all_sub_norm:
                            internal_val = internal_sub_map.get(
                                sub_norm, Decimal("0"))
                            external_val = external_sub_map.get(
                                sub_norm, Decimal("0"))

                            subprogramme_label = pick_label_from_subs(
                                internal_subs, sub_norm, None)
                            if subprogramme_label is None:
                                subprogramme_label = pick_label_from_subs(
                                    external_subs, sub_norm, sub_norm)

                            ValidationResult.objects.create(
                                validation_run=validation_run,
                                province="NATIONAL",
                                department=department,
                                programme=programme_label,
                                subprogramme=subprogramme_label,
                                level="SUBPROGRAMME",
                                internal_amount=internal_val,
                                external_amount=external_val,
                                is_valid=is_close(
                                    internal_val, external_val, tolerance),
                            )

        print(f"Validation completed for run {validation_run.id}")

    except Exception as e:
        print("Validation error:", str(e))
