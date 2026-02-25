from import_export import resources
from import_export.fields import Field
from import_export.instance_loaders import ModelInstanceLoader
from import_export.widgets import ForeignKeyWidget
from tablib import Databook
from tablib import Dataset

import budgetportal
from budgetportal.models import AENEData, DatasetCategory, DatasetUpload, ENEData, ConsolidationData, EPREData, BudgetVSActualNationalData, BudgetVSActualProvincialData, Organisation, VoteDocumentUpload, Department, VoteDocument, FinancialYear, Sphere, Government, Dataset, DatasetResource
from budgetportal.dataset_uploading import preprocess													

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


def import_dataset(obj_id):
    obj = DatasetUpload.objects.get(id=obj_id)
    file = obj.file.read()

    data_book = Databook().load(file, "xlsx")
    dataset = data_book.sheets()[0]

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
                "functionGroup1", "functionGroup2", "financialYear",
                "budgetPhase", "value"
            ],
        },
        "Budget-vs-Actual-National": {
            "headers": BUDGET_ACTUAL_HEADERS,
            "model": BudgetVSActualNationalData,
            "resource": BudgetVSActualResource,
            "fields": [
                "government", "voteNumber", "progNumber", "department",
                "programme", "subprogNumber", "subprogramme",
                "economicClassification1", "economicClassification2",
                "economicClassification3", "economicClassification4",
                "economicClassification5", "functionGroup1",
                "financialYear", "budgetPhase", "amountKind", "value"
            ],
        },
        "Budget-vs-Actual-Provincial": {
            "headers": BUDGET_ACTUAL_HEADERS,
            "model": BudgetVSActualProvincialData,
            "resource": BudgetVSActualResource,
            "fields": [
                "government", "voteNumber", "progNumber", "department",
                "programme", "subprogNumber", "subprogramme",
                "economicClassification1", "economicClassification2",
                "economicClassification3", "economicClassification4",
                "economicClassification5", "functionGroup1",
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
    resource_class = config["resource"]
    fields = config["fields"]

    # Preprocess and clean data
    preprocessed_dataset = preprocess(dataset, headers)
    # Create model objects
    
    header_to_field = dict(zip(headers, fields))

    objects_to_create = [
        model_class(**{header_to_field[k]: v for k, v in item.items()})
        for item in preprocessed_dataset
    ]

    financialYear = obj.financialYear.slug.split("-")[0]  # Extract year from slug like "2023-24"

    model_class.objects.filter(budgetYear=financialYear).delete()

    # model_class.objects.bulk_create(objects_to_create)

    # # Prepare dataset for import-export validation
    # dataset_import = Dataset()
    # if preprocessed_dataset:
    #     dataset_import.headers = preprocessed_dataset[0].keys()
    #     for row in preprocessed_dataset:
    #         dataset_import.append(row.values())

    # # Use correct resource dynamically
    # resource = resource_class()
    # result = resource.import_data(dataset_import, dry_run=True)
    
    # if result.has_errors():
    #     print("Import errors found:", result.invalid_rows)
    #     return result

    organisation = Organisation.objects.get(id=1)
    

    if obj.type in ["ENE", "AENE", "Consolidation", "Budget-vs-Actual-National"]:
        sphere = Sphere.objects.get(name="National", financial_year=obj.financialYear)
    else:
        sphere = Sphere.objects.get(name="Provincial", financial_year=obj.financialYear)

    if obj.type == 'ENE':
        title = 'Estimates of National Expenditure'
        category = DatasetCategory.objects.get(title=title) 
        formatted_title = f"{title} {obj.financialYear.slug}"
        desciption = formatted_title
        short_description = formatted_title
    elif obj.type == 'AENE': 
        title = 'Adjusted Estimates of National Expenditure'
        category = DatasetCategory.objects.get(title=title)
        formatted_title = f"{title} {obj.financialYear.slug}"
        desciption = formatted_title
        short_description = formatted_title
    elif obj.type == 'Consolidation': 
        title = 'Consolidated Expenditure'
        category = DatasetCategory.objects.get(title=title) 
        formatted_title = f"{title} {obj.financialYear.slug}"
        desciption = formatted_title
        short_description = formatted_title
    elif obj.type == 'EPRE': 
        title = 'Estimates of Provincial Revenue and Expenditure'
        category = DatasetCategory.objects.get(title=title)
        formatted_title = f"{title} {obj.financialYear.slug}"
        desciption = formatted_title
        short_description = formatted_title
    elif obj.type == 'Budget-vs-Actual-National':
        title = 'Budgeted vs Actual National Expenditure'
        category = DatasetCategory.objects.get(title=title)
        formatted_title = f"{title} {obj.financialYear.slug}"
        desciption = formatted_title
        short_description = formatted_title
    elif obj.type == 'Budget-vs-Actual-Provincial':
        title = 'Budgeted and Actual Provincial Expenditure'
        category = DatasetCategory.objects.get(title=title)
        formatted_title = f"{title} {financialYear.slug}"
        desciption = formatted_title
        short_description = formatted_title
        category = DatasetCategory.objects.get(title='Budgeted and Actual Provincial Expenditure')

    new_dataset = Dataset.objects.create(
        title=formatted_title,
        short_description=short_description,
        description=desciption,
        organisation=organisation,
        visibility=True,
        financial_year=obj.financialYear,
        sphere=sphere,
        # government_functions=gov_fn,  # can be None
        # dimensions=dimension,         # can be None
        province="South Africa",
        dataset_category=category,    # optional if you want explicit
    )

    DatasetResource.objects.create(
        fileName=title,
        description=formatted_title,
        # path=obj.file.path,
        format="XLSX",
        dataset=new_dataset,
        file=obj.file
    )


    return resource.import_data(dataset_import, dry_run=False)



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
    functionGroup2 = Field(column_name="FunctionGroup2")
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
