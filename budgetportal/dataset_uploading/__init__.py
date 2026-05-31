def normalize_header(header):
    if header is None:
        return ""
    return str(header).strip()


def check_input_column_order(input_headers, base_headers, dataset_type=None):
    actual_headers = [normalize_header(header) for header in (input_headers or [])]
    actual_headers = actual_headers[: len(base_headers)]
    expected_headers = [normalize_header(header) for header in base_headers]

    if actual_headers != expected_headers:
        label = f" for {dataset_type}" if dataset_type else ""
        raise ValueError(
            "Invalid upload columns"
            f"{label}. Expected columns: {', '.join(expected_headers)}. "
            f"Found columns: {', '.join(actual_headers)}."
        )


def preprocess(input_dataset, base_headers, dataset_type=None):
    check_input_column_order(input_dataset.headers, base_headers, dataset_type)
    output_dataset = []
    for row in input_dataset:
        try:
            if not row_is_empty(row):
                processed_dict = preprocess_row(row, base_headers)
                output_dataset.append(processed_dict)
        except Exception as e:
            print(f"Error occurred while processing row: {row}")
            print(f"Error: {e}")
    
    return output_dataset

def row_is_empty(row):
    return not any(row)


def preprocess_row(row, base_headers):
    return {
        base_headers[i]: row[i] if i < len(row) else None
        for i in range(len(base_headers))
    }
