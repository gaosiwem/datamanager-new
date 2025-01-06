from import_export import resources
from import_export.fields import Field
from import_export.instance_loaders import ModelInstanceLoader
from import_export.widgets import ForeignKeyWidget
from tablib import Databook
from tablib import Dataset

from budgetportal.models import DatasetUpload, ENEData, ConsolidationData, EPREData, BudgetVSActualNationalData, BudgetVSActualProvincialData
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


def import_dataset(obj_id):
    
    obj = DatasetUpload.objects.get(id=obj_id)
    
    file = obj.file.read()
    data_book = Databook().load(file, "xlsx")
    dataset = data_book.sheets()[0]
    preprocessed_dataset = None

    if obj.type == "ENE":
        preprocessed_dataset = preprocess(dataset, ENE_HEADERS)

        ENEData.objects.all().delete()
        for item in preprocessed_dataset:
            ENEData.objects.create(
                voteNumber=item["VoteNumber"],
                progNumber=item["ProgNumber"],
                department=item["Department"],
                programme=item["Programme"],
                subprogNumber=item["SubprogNumber"],
                subprogramme=item["Subprogramme"],
                economicClassification1=item[
                    "EconomicClassification1"],
                economicClassification2=item[
                    "EconomicClassification2"],
                economicClassification3=item[
                    "EconomicClassification3"],
                economicClassification4=item[
                    "EconomicClassification4"],
                economicClassification5=item[
                    "EconomicClassification5"],
                functionGroup1=item["FunctionGroup1"],
                financialYear=item["FinancialYear"],
                budgetPhase=item["BudgetPhase"],
                value=item["Value"],
            )

        resource = ENEResource()
        return resource.import_data(preprocessed_dataset)

    elif obj.type == "Consolidation":
        preprocessed_dataset = preprocess(dataset, CONSOLIDATED_HEADERS)
        ConsolidationData.objects.all().delete()
        for item in preprocessed_dataset:
            ConsolidationData.objects.create(
                functionGroup=item["FunctionGroup"],
                economicClassification2=item[
                    "EconomicClassification2"],
                economicClassification3=item[
                    "EconomicClassification3"],                
                financialYear=item["FinancialYear"],
                value=item["Value"],
            )

        resource = ConsolidationResource()
        return resource.import_data(preprocessed_dataset)
    
    elif obj.type == "EPRE":
        preprocessed_dataset = preprocess(dataset, EPRE_HEADERS)

        EPREData.objects.all().delete()
        for item in preprocessed_dataset:
            EPREData.objects.create(
                government=item["Government"],
                voteNumber=item["VoteNumber"],
                progNumber=item["ProgNumber"],
                department=item["Department"],
                programme=item["Programme"],
                subprogNumber=item["SubprogNumber"],
                subprogramme=item["Subprogramme"],
                economicClassification1=item[
                    "EconomicClassification1"],
                economicClassification2=item[
                    "EconomicClassification2"],
                economicClassification3=item[
                    "EconomicClassification3"],
                economicClassification4=item[
                    "EconomicClassification4"],
                economicClassification5=item[
                    "EconomicClassification5"],
                functionGroup1=item["FunctionGroup1"],
                functionGroup2=item["FunctionGroup2"],
                financialYear=item["FinancialYear"],
                budgetPhase=item["BudgetPhase"],
                value=item["Value"],
            )

        resource = EPREResource()
        return resource.import_data(preprocessed_dataset)

    elif obj.type == "Budget-vs-Actual-National":
        preprocessed_dataset = preprocess(dataset, BUDGET_ACTUAL_HEADERS)

        BudgetVSActualNationalData.objects.all().delete()
        for item in preprocessed_dataset:
            BudgetVSActualNationalData.objects.create(
                government=item["Government"],
                voteNumber=item["VoteNumber"],
                progNumber=item["ProgNumber"],
                department=item["Department"],
                programme=item["Programme"],
                subprogNumber=item["SubprogNumber"],
                subprogramme=item["Subprogramme"],
                economicClassification1=item[
                    "EconomicClassification1"],
                economicClassification2=item[
                    "EconomicClassification2"],
                economicClassification3=item[
                    "EconomicClassification3"],
                economicClassification4=item[
                    "EconomicClassification4"],
                economicClassification5=item[
                    "EconomicClassification5"],
                functionGroup1=item["FunctionGroup1"],
                financialYear=item["FinancialYear"],
                budgetPhase=item["BudgetPhase"],
                amountKind=item["AmountKind"],
                value=item["Value"],                
            )

        resource = BudgetVSActualResource()
        return resource.import_data(preprocessed_dataset)
    elif obj.type == "Budget-vs-Actual-Provincial":
        preprocessed_dataset = preprocess(dataset, BUDGET_ACTUAL_HEADERS)

        BudgetVSActualProvincialData.objects.all().delete()
        for item in preprocessed_dataset:
            BudgetVSActualProvincialData.objects.create(
                government=item["Government"],
                voteNumber=item["VoteNumber"],
                progNumber=item["ProgNumber"],
                department=item["Department"],
                programme=item["Programme"],
                subprogNumber=item["SubprogNumber"],
                subprogramme=item["Subprogramme"],
                economicClassification1=item[
                    "EconomicClassification1"],
                economicClassification2=item[
                    "EconomicClassification2"],
                economicClassification3=item[
                    "EconomicClassification3"],
                economicClassification4=item[
                    "EconomicClassification4"],
                economicClassification5=item[
                    "EconomicClassification5"],
                functionGroup1=item["FunctionGroup1"],
                financialYear=item["FinancialYear"],
                budgetPhase=item["BudgetPhase"],
                amountKind=item["AmountKind"],
                value=item["Value"],                
            )

        resource = BudgetVSActualResource()
        return resource.import_data(preprocessed_dataset)


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
    budgetPhase = Field(column_name="BudgetPhase")
    value = Field(column_name="Value")    

    class Meta:
        model = ENEData
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
