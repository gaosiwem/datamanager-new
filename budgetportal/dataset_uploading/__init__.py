from budgetportal import models
from import_export import resources
from import_export.fields import Field
from import_export.instance_loaders import ModelInstanceLoader
from import_export.widgets import ForeignKeyWidget
from tablib import Databook
from tablib import Dataset

def preprocess(input_dataset, base_headers):
    # We're going to assume things about the order of columns so ensure they're
    # in the order we expect.

    # check_input_column_order(input_dataset.headers)
    # implementor_column_indexes = get_implementor_column_indexes(
    #     input_dataset.headers)

    output_dataset = []
    for row in input_dataset:
        try:
            if not row_is_empty(row):
                processed_row = preprocess_row(row, base_headers)                
                # Convert row to dictionary with base_headers as keys
                processed_dict = {
                    base_headers[i]: processed_row[i] for i in range(len(base_headers))}
                
                output_dataset.append(processed_dict)
        except Exception:
            print("Error occured while processing")
            print(row)
    
    return output_dataset

def row_is_empty(row):
    return not any(row)


def preprocess_row(row, base_headers):
    base_columns = list(row[: len(base_headers)])
    return base_columns
