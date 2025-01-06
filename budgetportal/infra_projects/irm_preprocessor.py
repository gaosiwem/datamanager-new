import traceback
from tablib import Dataset

BASE_HEADERS = [
    "Project ID",
    "Project No",
    "Project Name",
    "Province",
    "Department",
    "Sector",
    "Local Municipality",
    "District Municipality",
    "Latitude",
    "Longitude",
    "Project Status",
    "Project Start Date",
    "Estimated Construction Start Date",
    "Estimated Project Completion Date",
    "Contracted Construction End Date",
    "Estimated Construction End Date",
    "Professional Fees",
    "Construction Costs",
    "Variation Orders",
    "Total Project Cost",
    "Project Expenditure from Previous Financial Years (Professional Fees)",
    "Project Expenditure from Previous Financial Years (Construction Costs)",
    "Project Expenditure from Previous Financial Years (TOTAL)",
    "Project Expenditure (TOTAL)",
    "Main Budget Appropriation (Professional Fees)",
    "Adjustment Budget Appropriation (Professional Fees)",  
    "Main Budget Appropriation (Construction Costs)",
    "Adjustment Budget Appropriation (Construction Costs)",
    "Main Budget Appropriation (TOTAL)",
    "Adjustment Budget Appropriation (TOTAL)",
    "Actual Expenditure Q1",
    "Actual Expenditure Q2",
    "Actual Expenditure Q3",
    "Actual Expenditure Q4",
    "Budget Programme",
    "Primary Funding Source",
    "Nature of Investment",
    "Funding Status",
]
REPEATED_IMPLEMENTOR_HEADER = "Project Contractor"
EXTRA_IMPLEMENTOR_HEADER = "Other parties"
IMPLEMENTORS = ["Program Implementing Agent", "Principal Agent", "Main Contractor"]
IMPLEMENTOR_HEADERS = IMPLEMENTORS + [EXTRA_IMPLEMENTOR_HEADER]
OUTPUT_HEADERS = BASE_HEADERS + IMPLEMENTORS


class InputException(Exception):
    pass


def preprocess(input_dataset):
    """
    Given a tablib dataset with headers BASE_HEADERS and any number of coumns
    headed REPEATED_IMPLEMENTOR_HEADER, this returns a tablib dataset with headers
    BASE_HEADERS + IMPLEMENTOR_HEADERS + EXTRA_IMPLEMENTOR_HEADER where
    the REPEATED_IMPLEMENTOR_HEADER columns have been transformed into the columns
    headed by IMPLEMENTOR_HEADERS + EXTRA_IMPLEMENTOR_HEADER
    """
    # We're going to assume things about the order of columns so ensure they're
    # in the order we expect.
    output_dataset = []
    for row in input_dataset:
        try:
            if not row_is_empty(row):
                processed_row = preprocess_row(row, OUTPUT_HEADERS)
                # Convert row to dictionary with base_headers as keys
                processed_dict = {
                    OUTPUT_HEADERS[i]: processed_row[i] for i in range(len(OUTPUT_HEADERS))}

                output_dataset.append(processed_dict)
        except Exception:
            print("Error occured while processing")
            print(row)
    return output_dataset

# def preprocess(input_dataset):
#     """
#     Given a tablib dataset with headers BASE_HEADERS and any number of coumns
#     headed REPEATED_IMPLEMENTOR_HEADER, this returns a tablib dataset with headers
#     BASE_HEADERS + IMPLEMENTOR_HEADERS + EXTRA_IMPLEMENTOR_HEADER where
#     the REPEATED_IMPLEMENTOR_HEADER columns have been transformed into the columns
#     headed by IMPLEMENTOR_HEADERS + EXTRA_IMPLEMENTOR_HEADER
#     """
#     # We're going to assume things about the order of columns so ensure they're
#     # in the order we expect.
#     # check_input_column_order(input_dataset.headers)
#     # implementor_column_indexes = get_implementor_column_indexes(input_dataset.headers)
#     # output_dataset = Dataset(headers=BASE_HEADERS + IMPLEMENTOR_HEADERS)
#     # for row in input_dataset:
#     #     if not row_is_empty(row):
#     #         output_dataset.append(preprocess_row(row, implementor_column_indexes))
#     # return output_dataset

#     output_dataset = []

#     check_input_column_order(input_dataset.headers)
#     implementor_column_indexes = get_implementor_column_indexes(input_dataset.headers)
#     output_dataset = Dataset(headers=BASE_HEADERS + IMPLEMENTOR_HEADERS)
#     print(output_dataset)
#     print(input_dataset)
#     for row in input_dataset:
#         try:
#             if not row_is_empty(row):
#                 processed_row = preprocess_row(row, OUTPUT_HEADERS)
#                 # Check for length mismatch
#                 if len(OUTPUT_HEADERS) != len(processed_row):
#                     raise ValueError(
#                         f"Header-Row Length Mismatch: OUTPUT_HEADERS has {len(OUTPUT_HEADERS)} items "
#                         f"but processed_row has {len(processed_row)} items. Row: {row}"
#                     )

#                 # Create dictionary
#                 processed_dict = {
#                     OUTPUT_HEADERS[i]: processed_row[i] for i in range(len(OUTPUT_HEADERS))
#                 }
#                 output_dataset.append(processed_dict)
#         except Exception as e:
#             print(f"Error occurred while processing row: {row}")
#             print(f"Exception: {e}")
#             traceback.print_exc()

#     return output_dataset


def row_is_empty(row):
    return not any(row)


def check_input_column_order(input_headers):
    for i, header in enumerate(input_headers):
        if i < len(BASE_HEADERS):
            expected_header = BASE_HEADERS[i]
            actual_header = input_headers[i]
        else:
            expected_header = REPEATED_IMPLEMENTOR_HEADER
            actual_header = input_headers[i]
        if actual_header != expected_header:
            raise InputException(
                "Expected header %s in column %d but got %s"
                % (expected_header, i + 1, actual_header)
            )


def get_implementor_column_indexes(headers):
    return [
        i
        for i in range(len(headers))
        if headers[i].strip() == REPEATED_IMPLEMENTOR_HEADER
    ]


# def preprocess_row(row, implementor_column_indexes):
#     base_columns = list(row[: len(BASE_HEADERS)])
#     implementor_columns = get_row_implementors(row, implementor_column_indexes)
#     return base_columns + implementor_columns


def preprocess_row(row, base_headers):
    base_columns = list(row[: len(base_headers)])
    return base_columns

def get_row_implementors(row, implementor_column_indexes):
    prefixes = {header.lower() + ":": header for header in IMPLEMENTOR_HEADERS}    
    row_implementors = {header: [] for header in IMPLEMENTOR_HEADERS}    
    for col in implementor_column_indexes:
        cell = row[col]
        if cell is not None and cell.strip():
            for prefix in prefixes:
                if cell.lower().strip().startswith(prefix):
                    implementor_value = cell.split(":")[1].strip()
                    row_implementors[prefixes[prefix]].append(implementor_value)
                    break
            else:

                # Implementor hasn't been found, append to "Other parties"
                row_implementors[EXTRA_IMPLEMENTOR_HEADER].append(cell)

    return ["\n".join(row_implementors[k]) for k in IMPLEMENTOR_HEADERS]
