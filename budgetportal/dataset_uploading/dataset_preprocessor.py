import csv
import os
from import_export import resources
from import_export.fields import Field
from import_export.instance_loaders import ModelInstanceLoader
from import_export.widgets import ForeignKeyWidget
from tablib import Databook
from tablib import Dataset as TablibDataset

import budgetportal
from budgetportal.models import AENEData, DatasetCategory, DatasetUpload, ENEData, ConsolidationData, EPREData, BudgetVSActualNationalData, BudgetVSActualProvincialData, Organisation, VoteDocumentUpload, Department, VoteDocument, FinancialYear, Sphere, Government, Dataset, DatasetResource
from budgetportal.dataset_uploading import preprocess													
from django.db import transaction

DATASET_BULK_CREATE_BATCH_SIZE = 5000
SQL_SERVER_SAFE_PARAM_LIMIT = 2000
CHUNK_LOG_INTERVAL = 100

ENE_HEADERS = [
    "VoteNumber",
    "Department",
    "ProgNumber",
    "Programme",
    "SubprogNumber",
    "Subprogramme",
    "EconomicClassification1",
    "EconomicClassification2",
    "EconomicClassification3",
    "EconomicClassification4",
    "EconomicClassification5",
    "FunctionGroup1",
    "BudgetYear",
    "FinancialYear",
    "BudgetPhase",
    "Value"
]

EPRE_HEADERS = [
    "Government",
    "VoteNumber",
    "Department",
    "ProgNumber",
    "Programme",
    "SubprogNumber",
    "Subprogramme",
    "EconomicClassification1",
    "EconomicClassification2",
    "EconomicClassification3",
    "EconomicClassification4",
    "EconomicClassification5",
    "FunctionGroup1",
    "FunctionGroup2",
    "BudgetYear",
    "FinancialYear",
    "BudgetPhase",
    "Value"
]

BUDGET_ACTUAL_HEADERS = [
    "Government",
    "VoteNumber",
    "Department",
    "ProgNumber",
    "Programme",
    "SubprogNumber",
    "Subprogramme",
    "EconomicClassification1",
    "EconomicClassification2",
    "EconomicClassification3",
    "EconomicClassification4",
    "EconomicClassification5",
    "FunctionGroup1",
    "BudgetYear",
    "FinancialYear",
    "BudgetPhase",
    "AmountKind",
    "Value"
]

CONSOLIDATED_HEADERS = [
    "FunctionGroup",
    "EconomicClassification2",
    "EconomicClassification3",
    "FinancialYear",
    "Value"
]

VOTEDOCUMENTSDATA_HEADERS = [   
    "government" ,
    "department_name",
    "dataset_name",
    "dataset_title",
    "dataset_category",
    "document_type",
    "document_url",
    "financial_year"
]

AENE_HEADERS = [
    "VoteNumber",
    "Department",
    "ProgNumber",
    "Programme",
    "SubprogNumber",
    "Subprogramme",
    "EconomicClassification1",
    "EconomicClassification2",
    "EconomicClassification3",
    "EconomicClassification4",
    "EconomicClassification5",
    "FinancialYear",
    "BudgetPhase",
    "AmountKind",
    "Value"
]


def log_progress(progress_callback, message):
    print("[dataset_importer] {}".format(message), flush=True)
    if progress_callback:
        progress_callback(message)


def get_or_create_dataset_category(title, description="", category_type="Original Budget", alternate_titles=None):
    alternate_titles = alternate_titles or []

    for candidate_title in [title] + list(alternate_titles):
        category = DatasetCategory.objects.filter(title=candidate_title).first()
        if category:
            return category

    category, _ = DatasetCategory.objects.get_or_create(
        title=title,
        defaults={
            "description": description or title,
            "type": category_type,
        },
    )
    return category


def chunked(iterable, size):
    for start in range(0, len(iterable), size):
        yield iterable[start:start + size]


def safe_bulk_create_batch_size(field_count):
    if field_count <= 0:
        return DATASET_BULK_CREATE_BATCH_SIZE
    sql_server_batch_size = max(1, SQL_SERVER_SAFE_PARAM_LIMIT // field_count)
    return min(DATASET_BULK_CREATE_BATCH_SIZE, sql_server_batch_size)


def load_tablib_dataset(upload_obj, file_bytes, progress_callback=None):
    file_extension = os.path.splitext(upload_obj.file.name)[1].lower()
    if file_extension == ".csv":
        log_progress(progress_callback, "Detected CSV upload format")
        decoded = file_bytes.decode("utf-8-sig")
        reader = csv.reader(decoded.splitlines())
        rows = list(reader)
        if not rows:
            raise ValueError("Uploaded CSV file is empty.")
        dataset = TablibDataset()
        dataset.headers = rows[0]
        for row in rows[1:]:
            dataset.append(row)
        return dataset, "CSV"

    log_progress(progress_callback, "Detected XLSX upload format")
    data_book = Databook().load(file_bytes, "xlsx")
    return data_book.sheets()[0], "XLSX"


def import_dataset(obj_id, progress_callback=None, excel_file=None):
    obj = DatasetUpload.objects.get(id=obj_id)
    log_progress(progress_callback, "Reading DatasetUpload {} ({})".format(obj.id, obj.type))
    file = obj.file.read()
    dataset, upload_format = load_tablib_dataset(obj, file, progress_callback=progress_callback)

    # Central configuration for all dataset types
    DATASET_CONFIG = {
        "ENE": {
            "headers": ENE_HEADERS,
            "model": ENEData,
            "resource": ENEResource,
            "fields": [
                "voteNumber", "department", "progNumber", "programme",
                "subprogNumber", "subprogramme", "economicClassification1",
                "economicClassification2", "economicClassification3",
                "economicClassification4", "economicClassification5",
                "functionGroup1", "budgetYear", "financialYear", "budgetPhase", "value"
            ],
        },
        "AENE": {
            "headers": AENE_HEADERS,
            "model": AENEData,
            "resource": AENEResource,
            "fields": [
                "voteNumber", "department", "progNumber", "programme",
                "subprogNumber", "subprogramme", "economicClassification1",
                "economicClassification2", "economicClassification3",
                "economicClassification4", "economicClassification5",
                "financialYear", "budgetPhase", "amountKind", "value"
            ],
        },
        "Consolidation": {
            "headers": CONSOLIDATED_HEADERS,
            "model": ConsolidationData,
            "resource": ConsolidationResource,
            "fields": [
                "functionGroup", "economicClassification2",
                "economicClassification3", "financialYear", "value"
            ],
        },
        "EPRE": {
            "headers": EPRE_HEADERS,
            "model": EPREData,
            "resource": EPREResource,
            "fields": [
                "government", "voteNumber", "department", "progNumber", "programme",
                "subprogNumber", "subprogramme", "economicClassification1",
                "economicClassification2", "economicClassification3",
                "economicClassification4", "economicClassification5",
                "functionGroup1", "functionGroup2", "budgetYear","financialYear",
                "budgetPhase", "value"
            ],
        },
        "Budget-vs-Actual-National": {
            "headers": BUDGET_ACTUAL_HEADERS,
            "model": BudgetVSActualNationalData,
            "resource": BudgetVSActualResource,
            "fields": [
                "government", "voteNumber", "department", "progNumber",
                "programme", "subprogNumber", "subprogramme",
                "economicClassification1", "economicClassification2",
                "economicClassification3", "economicClassification4",
                "economicClassification5", "functionGroup1", "budgetYear",
                "financialYear", "budgetPhase", "amountKind", "value"
            ],
        },
        "Budget-vs-Actual-Provincial": {
            "headers": BUDGET_ACTUAL_HEADERS,
            "model": BudgetVSActualProvincialData,
            "resource": BudgetVSActualResource,
            "fields": [
                "government", "voteNumber", "department", "progNumber",
                "programme", "subprogNumber", "subprogramme",
                "economicClassification1", "economicClassification2",
                "economicClassification3", "economicClassification4",
                "economicClassification5", "functionGroup1","budgetYear",
                "financialYear", "budgetPhase", "amountKind", "value"
            ],
        },
    }

    # Select correct configuration
    config = DATASET_CONFIG.get(obj.type)
    if not config:
        raise ValueError(f"Unsupported dataset type: {obj.type}")

    headers = config["headers"]
    model_class = config["model"]
    fields = config["fields"]

    # Preprocess and clean data
    preprocessed_dataset = preprocess(dataset, headers, obj.type)
    log_progress(progress_callback, "Preprocessed {} rows".format(len(preprocessed_dataset)))
    header_to_field = dict(zip(headers, fields))
    financialYear = obj.financialYear.slug.split("-")[0]  # Extract year from slug like "2023-24"

    imported_budget_years = sorted(
        {
            str(item.get("BudgetYear") or financialYear)
            for item in preprocessed_dataset
        }
    )
    log_progress(
        progress_callback,
        "Prepared to import budget years: {}".format(", ".join(imported_budget_years)),
    )

    # Keep the high-volume row replacement outside a long-lived explicit transaction.
    # On SQL Server, holding delete + bulk insert + metadata updates in one atomic block
    # can escalate locks and make unrelated requests wait behind the import.
    deleted_count, _ = model_class.objects.filter(budgetYear__in=imported_budget_years).delete()
    log_progress(
        progress_callback,
        "Deleted {} existing {} rows for budget years {}".format(
            deleted_count,
            model_class.__name__,
            ", ".join(imported_budget_years),
        ),
    )
    # Use the model's inserted fields rather than the input headers.  AENE has
    # no BudgetYear column in its upload schema, but the importer supplies that
    # model field before bulk insertion; counting only the CSV columns exceeds
    # SQL Server's parameter limit.
    inserted_field_count = len(model_class._meta.fields) - 1  # Exclude auto PK.
    bulk_create_batch_size = safe_bulk_create_batch_size(inserted_field_count)
    total_chunks = max(
        1,
        (len(preprocessed_dataset) + bulk_create_batch_size - 1) // bulk_create_batch_size,
    )
    for index, item_chunk in enumerate(
        chunked(preprocessed_dataset, bulk_create_batch_size), start=1
    ):
        object_chunk = []
        for item in item_chunk:
            row_data = {header_to_field[k]: v for k, v in item.items()}
            row_data.setdefault("budgetYear", financialYear)
            object_chunk.append(model_class(**row_data))
        model_class.objects.bulk_create(
            object_chunk,
            batch_size=bulk_create_batch_size,
        )
        if (
            index == 1
            or index == total_chunks
            or index % CHUNK_LOG_INTERVAL == 0
        ):
            log_progress(
                progress_callback,
                "Inserted chunk {} of {} ({} rows) into {}".format(
                    index,
                    total_chunks,
                    len(object_chunk),
                    model_class.__name__,
                ),
            )

    organisation = Organisation.objects.get(id=1)

    if obj.type in ["ENE", "AENE", "Consolidation", "Budget-vs-Actual-National"]:
        sphere = Sphere.objects.get(name="National", financial_year=obj.financialYear)
    else:
        sphere = Sphere.objects.get(name="Provincial", financial_year=obj.financialYear)

    if obj.type == 'ENE':
        title = 'Estimates of National Expenditure'
        category = get_or_create_dataset_category(
            title,
            description=title,
            category_type="Original Budget",
        )
        formatted_title = f"{title} {obj.financialYear.slug}"
        desciption = formatted_title
        short_description = formatted_title
    elif obj.type == 'AENE': 
        title = 'Adjusted Estimates of National Expenditure'
        category = get_or_create_dataset_category(
            title,
            description=title,
            category_type="Adjusted Budget",
        )
        formatted_title = f"{title} {obj.financialYear.slug}"
        desciption = formatted_title
        short_description = formatted_title
    elif obj.type == 'Consolidation': 
        title = 'Consolidated Expenditure'
        category = get_or_create_dataset_category(
            title,
            description=title,
            category_type="Original Budget",
        )
        formatted_title = f"{title} {obj.financialYear.slug}"
        desciption = formatted_title
        short_description = formatted_title
    elif obj.type == 'EPRE': 
        title = 'Estimates of Provincial Revenue and Expenditure'
        category = get_or_create_dataset_category(
            title,
            description=title,
            category_type="Original Budget",
        )
        formatted_title = f"{title} {obj.financialYear.slug}"
        desciption = formatted_title
        short_description = formatted_title
    elif obj.type == 'Budget-vs-Actual-National':
        title = 'Budgeted vs Actual National Expenditure'
        category = get_or_create_dataset_category(
            title,
            description=title,
            category_type="Original Budget",
            alternate_titles=["Budgeted and Actual National Expenditure"],
        )
        formatted_title = f"{title} {obj.financialYear.slug}"
        desciption = formatted_title
        short_description = formatted_title
    elif obj.type == 'Budget-vs-Actual-Provincial':
        title = 'Budgeted and Actual Provincial Expenditure'
        category = get_or_create_dataset_category(
            title,
            description=title,
            category_type="Original Budget",
        )
        formatted_title = f"{title} {obj.financialYear.slug}"
        desciption = formatted_title
        short_description = formatted_title

    with transaction.atomic():
        new_dataset, created_dataset = Dataset.objects.update_or_create(
            title=formatted_title,
            financial_year=obj.financialYear,
            sphere=sphere,
            dataset_category=category,
            defaults={
                "short_description": short_description,
                "description": desciption,
                "organisation": organisation,
                "visibility": True,
                "province": "South Africa",
            },
        )

        DatasetResource.objects.filter(dataset=new_dataset, format="XLSX").delete()
        DatasetResource.objects.filter(dataset=new_dataset, format="CSV").delete()
        DatasetResource.objects.create(
            fileName=title,
            description=formatted_title,
            format=upload_format,
            dataset=new_dataset,
            file=obj.file
        )
        if excel_file:
            DatasetResource.objects.create(
                fileName=title,
                description=formatted_title,
                format="XLSX",
                dataset=new_dataset,
                file=excel_file,
            )
    log_progress(
        progress_callback,
        "Updated dataset {} ({})".format(new_dataset.id, formatted_title),
    )

    return {
        "dataset_id": new_dataset.id,
        "dataset_upload_id": obj.id,
        "imported_rows": len(preprocessed_dataset),
        "created_dataset": created_dataset,
    }



# def import_dataset(obj_id):
    
#     obj = DatasetUpload.objects.get(id=obj_id)
    
#     file = obj.file.read()
#     data_book = Databook().load(file, "xlsx")
#     dataset = data_book.sheets()[0]
#     preprocessed_dataset = None

#     if obj.type == "ENE":
#         preprocessed_dataset = preprocess(dataset, ENE_HEADERS)

#         # ENEData.objects.all().delete()
#         for item in preprocessed_dataset:
#             ENEData.objects.create(
#                 voteNumber=item["VoteNumber"],
#                 progNumber=item["ProgNumber"],
#                 department=item["Department"],
#                 programme=item["Programme"],
#                 subprogNumber=item["SubprogNumber"],
#                 subprogramme=item["Subprogramme"],
#                 economicClassification1=item[
#                     "EconomicClassification1"],
#                 economicClassification2=item[
#                     "EconomicClassification2"],
#                 economicClassification3=item[
#                     "EconomicClassification3"],
#                 economicClassification4=item[
#                     "EconomicClassification4"],
#                 economicClassification5=item[
#                     "EconomicClassification5"],
#                 functionGroup1=item["FunctionGroup1"],
#                 financialYear=item["FinancialYear"],
#                 budgetPhase=item["BudgetPhase"],
#                 value=item["Value"],
#             )   

#     if obj.type == "AENE":
#         preprocessed_dataset = preprocess(dataset, AENE_HEADERS)

#         for item in preprocessed_dataset:
#             AENEData.objects.create(
#                 voteNumber=item["VoteNumber"],
#                 progNumber=item["ProgNumber"],
#                 department=item["Department"],
#                 programme=item["Programme"],
#                 subprogNumber=item["SubprogNumber"],
#                 subprogramme=item["Subprogramme"],
#                 economicClassification1=item[
#                     "EconomicClassification1"],
#                 economicClassification2=item[
#                     "EconomicClassification2"],
#                 economicClassification3=item[
#                     "EconomicClassification3"],
#                 economicClassification4=item[
#                     "EconomicClassification4"],
#                 economicClassification5=item[
#                     "EconomicClassification5"],                
#                 financialYear=item["FinancialYear"],
#                 budgetPhase=item["BudgetPhase"],
#                 amountKind=item["AmountKind"],
#                 value=item["Value"],
#             )
        

#     elif obj.type == "Consolidation":
#         preprocessed_dataset = preprocess(dataset, CONSOLIDATED_HEADERS)
#         # ConsolidationData.objects.all().delete()
#         for item in preprocessed_dataset:
#             ConsolidationData.objects.create(
#                 functionGroup=item["FunctionGroup"],
#                 economicClassification2=item[
#                     "EconomicClassification2"],
#                 economicClassification3=item[
#                     "EconomicClassification3"],                
#                 financialYear=item["FinancialYear"],
#                 value=item["Value"],
#             )
    
#     elif obj.type == "EPRE":
#         preprocessed_dataset = preprocess(dataset, EPRE_HEADERS)

#         # EPREData.objects.all().delete()
#         for item in preprocessed_dataset:
#             EPREData.objects.create(
#                 government=item["Government"],
#                 voteNumber=item["VoteNumber"],
#                 progNumber=item["ProgNumber"],
#                 department=item["Department"],
#                 programme=item["Programme"],
#                 subprogNumber=item["SubprogNumber"],
#                 subprogramme=item["Subprogramme"],
#                 economicClassification1=item[
#                     "EconomicClassification1"],
#                 economicClassification2=item[
#                     "EconomicClassification2"],
#                 economicClassification3=item[
#                     "EconomicClassification3"],
#                 economicClassification4=item[
#                     "EconomicClassification4"],
#                 economicClassification5=item[
#                     "EconomicClassification5"],
#                 functionGroup1=item["FunctionGroup1"],
#                 functionGroup2=item["FunctionGroup2"],
#                 financialYear=item["FinancialYear"],
#                 budgetPhase=item["BudgetPhase"],
#                 value=item["Value"],
#             )

#     elif obj.type == "Budget-vs-Actual-National":
#         preprocessed_dataset = preprocess(dataset, BUDGET_ACTUAL_HEADERS)

#         # BudgetVSActualNationalData.objects.all().delete()
#         for item in preprocessed_dataset:
#             BudgetVSActualNationalData.objects.create(
#                 government=item["Government"],
#                 voteNumber=item["VoteNumber"],
#                 progNumber=item["ProgNumber"],
#                 department=item["Department"],
#                 programme=item["Programme"],
#                 subprogNumber=item["SubprogNumber"],
#                 subprogramme=item["Subprogramme"],
#                 economicClassification1=item[
#                     "EconomicClassification1"],
#                 economicClassification2=item[
#                     "EconomicClassification2"],
#                 economicClassification3=item[
#                     "EconomicClassification3"],
#                 economicClassification4=item[
#                     "EconomicClassification4"],
#                 economicClassification5=item[
#                     "EconomicClassification5"],
#                 functionGroup1=item["FunctionGroup1"],
#                 financialYear=item["FinancialYear"],
#                 budgetPhase=item["BudgetPhase"],
#                 amountKind=item["AmountKind"],
#                 value=item["Value"],                
#             )

#     elif obj.type == "Budget-vs-Actual-Provincial":
#         preprocessed_dataset = preprocess(dataset, BUDGET_ACTUAL_HEADERS)

#         # BudgetVSActualProvincialData.objects.all().delete()
#         for item in preprocessed_dataset:
#             BudgetVSActualProvincialData.objects.create(
#                 government=item["Government"],
#                 voteNumber=item["VoteNumber"],
#                 progNumber=item["ProgNumber"],
#                 department=item["Department"],
#                 programme=item["Programme"],
#                 subprogNumber=item["SubprogNumber"],
#                 subprogramme=item["Subprogramme"],
#                 economicClassification1=item[
#                     "EconomicClassification1"],
#                 economicClassification2=item[
#                     "EconomicClassification2"],
#                 economicClassification3=item[
#                     "EconomicClassification3"],
#                 economicClassification4=item[
#                     "EconomicClassification4"],
#                 economicClassification5=item[
#                     "EconomicClassification5"],
#                 functionGroup1=item["FunctionGroup1"],
#                 financialYear=item["FinancialYear"],
#                 budgetPhase=item["BudgetPhase"],
#                 amountKind=item["AmountKind"],
#                 value=item["Value"],                
#             )

#     dataset = Dataset()

#     if preprocessed_dataset:
#         dataset.headers = preprocessed_dataset[0].keys()  # Set headers

#         # Append rows
#         for row in preprocessed_dataset:
#             dataset.append(row.values())  # Add dat

#     resource = ENEResource()
#     result = resource.import_data(dataset, dry_run=True)  # Test first

#     print(result.has_errors())  # Check if any errors occur

#     if not result.has_errors():
#         return resource.import_data(dataset, dry_run=False)


def save_vote_documents_data(obj_id):
    
    obj = VoteDocumentUpload.objects.get(id=obj_id)
    
    file = obj.file.read()
    data_book = Databook().load(file, "xlsx")
    financialYear =  data_book.sheets()[0]["financial_year"][0]
    VoteDocument.objects.filter(slug=financialYear).delete()
    sheets = data_book.sheets()

    for sheet in sheets:
        
        preprocessed_dataset = None

        preprocessed_dataset = preprocess(sheet, VOTEDOCUMENTSDATA_HEADERS)
        
        for item in preprocessed_dataset:

            financialYears = FinancialYear.objects.filter(slug=item["financial_year"])

            if financialYears:
                selectedFinancialYear = financialYears.first()

                sphere = ""

                if item["government"] == "South Africa":
                    sphere = "national"
                else:
                    sphere = "provincial"

                spheres = Sphere.objects.filter(
                    slug=sphere, financial_year=selectedFinancialYear
                )

                if spheres:
                    selectedSphere = spheres.first()
                    governments = Government.objects.filter(sphere=selectedSphere)

                    if governments:
                        selectedGovernment = governments.first()

                        department_name = item["department_name"]

                        departments = Department.objects.filter(
                            name=department_name, government=selectedGovernment
                        )
                        selectedDepartment = None

                        if departments:
                            selectedDepartment = departments.first()

                            VoteDocument.objects.create(
                                department=selectedDepartment,
                                financialYear=selectedFinancialYear,
                                government=selectedGovernment,
                                dataset_name=item["dataset_name"],
                                dataset_title=item["dataset_title"],
                                dataset_category=DatasetCategory.objects.get(
                                    slug=item["dataset_category"]),
                                document_type=item["document_type"],
                                document_url=item["document_url"]
                            )

                            dataset = Dataset()

                            if preprocessed_dataset:
                                dataset.headers = preprocessed_dataset[0].keys()  # Set headers

                                # Append rows
                                for row in preprocessed_dataset:
                                    dataset.append(row.values())  # Add dat

                            resource = VoteDocumentResource()
                            result = resource.import_data(dataset, dry_run=True)  # Test first

                            if not result.has_errors():
                                resource.import_data(dataset, dry_run=False)          

class ENEResource(resources.ModelResource):
    voteNumber = Field(
        column_name="VoteNumber",
    )
    department = Field(
        column_name="Department",
    )
    progNumber = Field(
        column_name="ProgNumber",
    )
    programme = Field(column_name="Programme")
    subprogNumber = Field(column_name="SubprogNumber")
    subprogramme = Field(column_name="Subprogramme")
    economicClassification1 = Field(column_name="EconomicClassification1")
    economicClassification2 = Field(column_name="EconomicClassification2")
    economicClassification3 = Field(column_name="EconomicClassification3")
    economicClassification4 = Field(column_name="EconomicClassification4")
    economicClassification5 = Field(column_name="EconomicClassification5")
    functionGroup1 = Field(column_name="FunctionGroup1")
    financialYear = Field(column_name="FinancialYear")
    budgetYear = Field(column_name="BudgetYear")
    budgetPhase = Field(column_name="BudgetPhase")
    value = Field(column_name="Value")    

    class Meta:
        model = ENEData
        skip_unchanged = True
        report_skipped = False


class AENEResource(resources.ModelResource):
    voteNumber = Field(
        column_name="VoteNumber",
    )
    department = Field(
        column_name="Department",
    )
    progNumber = Field(
        column_name="ProgNumber",
    )
    programme = Field(column_name="Programme")
    subprogNumber = Field(column_name="SubprogNumber")
    subprogramme = Field(column_name="Subprogramme")
    economicClassification1 = Field(column_name="EconomicClassification1")
    economicClassification2 = Field(column_name="EconomicClassification2")
    economicClassification3 = Field(column_name="EconomicClassification3")
    economicClassification4 = Field(column_name="EconomicClassification4")
    economicClassification5 = Field(column_name="EconomicClassification5")    
    financialYear = Field(column_name="FinancialYear")
    budgetPhase = Field(column_name="BudgetPhase")
    amountKind = Field(column_name="AmountKind")
    value = Field(column_name="Value")

    class Meta:
        model = AENEData
        skip_unchanged = True
        report_skipped = False


class ConsolidationResource(resources.ModelResource):
    functionGroup = Field(column_name="FunctionGroup")
    economicClassification2 = Field(column_name="EconomicClassification2")
    economicClassification3 = Field(column_name="EconomicClassification3")
    financialYear = Field(column_name="FinancialYear")
    value = Field(column_name="Value")

    class Meta:
        model = ConsolidationData
        skip_unchanged = True
        report_skipped = False


class EPREResource(resources.ModelResource):
    
    government = Field(
        column_name="Government",
    )
    voteNumber = Field(
        column_name="VoteNumber",
    )
    department = Field(
        column_name="Department",
    )
    progNumber = Field(
        column_name="ProgNumber",
    )
    programme = Field(column_name="Programme")
    subprogNumber = Field(column_name="SubprogNumber")
    subprogramme = Field(column_name="Subprogramme")
    economicClassification1 = Field(column_name="EconomicClassification1")
    economicClassification2 = Field(column_name="EconomicClassification2")
    economicClassification3 = Field(column_name="EconomicClassification3")
    economicClassification4 = Field(column_name="EconomicClassification4")
    economicClassification5 = Field(column_name="EconomicClassification5")
    functionGroup1 = Field(column_name="FunctionGroup1")
    functionGroup2 = Field(column_name="FunctionGroup2")
    BudgetYear = Field(column_name="BudgetYear")    
    financialYear = Field(column_name="FinancialYear")
    budgetPhase = Field(column_name="BudgetPhase")
    value = Field(column_name="Value")

    class Meta:
        model = EPREData
        skip_unchanged = True
        report_skipped = False


class BudgetVSActualResource(resources.ModelResource):

    government = Field(
        column_name="Government",
    )
    voteNumber = Field(
        column_name="VoteNumber",
    )
    department = Field(
        column_name="Department",
    )
    progNumber = Field(
        column_name="ProgNumber",
    )
    programme = Field(column_name="Programme")
    subprogNumber = Field(column_name="SubprogNumber")
    subprogramme = Field(column_name="Subprogramme")
    economicClassification1 = Field(column_name="EconomicClassification1")
    economicClassification2 = Field(column_name="EconomicClassification2")
    economicClassification3 = Field(column_name="EconomicClassification3")
    economicClassification4 = Field(column_name="EconomicClassification4")
    economicClassification5 = Field(column_name="EconomicClassification5")
    functionGroup1 = Field(column_name="FunctionGroup1")
    budgetYear = Field(column_name="BudgetYear")
    financialYear = Field(column_name="FinancialYear")
    budgetPhase = Field(column_name="BudgetPhase")
    amountKind = Field(column_name="AmountKind")
    value = Field(column_name="Value")
    

    class Meta:
        model = EPREData
        skip_unchanged = True
        report_skipped = False

class VoteDocumentResource(resources.ModelResource):
    dataset_name = Field(column_name="dataset_name")
    financialYear = Field(column_name="financialYear")
    government = Field(column_name="government")
    dataset_title = Field(column_name="dataset_title")
    document_type = Field(column_name="document_type")
    document_url = Field(column_name="document_url")
    department = Field(column_name="department")

    class Meta:
        model = ConsolidationData
        skip_unchanged = True
        report_skipped = False
