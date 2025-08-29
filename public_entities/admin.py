import csv
from io import StringIO
import chardet
from django.contrib import admin
import os

from budgetportal.models import Department, FinancialYear, Government, Sphere
from public_entities.models import PublicEntity, PublicEntityExpenditure, PublicEntitiesFileUpload
from public_entities.import_export_admin import PublicEntityResource
from import_export.admin import ImportMixin

from django_q.tasks import async_task, fetch
from slugify import slugify


class PublicEntityExpenditureAdmin(admin.ModelAdmin):
    list_display = (
        "public_entity",
        "amount",
        "budget_phase",
        "expenditure_type",
        "economic_classification1",
        "economic_classification2",
        "economic_classification3",
        "economic_classification4",
        "economic_classification5",
        "economic_classification6",
        "consol_indi",
    )


def get_financial_year(full_text):
    print("Split")
    print(full_text.split("\n", 1)[1])
    financial_year = full_text.split("\n", 1)[1]
    financial_year = financial_year[: financial_year.index(" ")]
    financial_year = financial_year.strip()

    return financial_year

def get_sphere(full_text):
    line = full_text.split("\n", 2)[1]
    if "Provincial" in line:
        sphere = "Provincial"
    else:
        sphere = "National"

    return sphere

def make_financial_year(year):
    # Check if the input is a valid year
    try:
        year = int(year)
    except ValueError:
        return "Invalid year format"

    financial_year_str = f"{year - 1}-{str(year)[2:]}"

    return financial_year_str


def generate_import_report(reportArray
):
    report = ""
    for r in reportArray:
        report += f"* {r} {os.linesep}"

    return report

def save_imported_public_entities(obj_id):
    # read file
    obj_to_update = PublicEntitiesFileUpload.objects.get(id=obj_id)
    file_content = obj_to_update.file.read()

    detected_encoding = chardet.detect(file_content)['encoding']

    print(f"Detected encoding: {detected_encoding}")

    full_text = file_content.decode(detected_encoding)

    # clean the csv & extract data
    # financial_year = get_financial_year(full_text)

    # print(f"Financial Year: {financial_year}")

    sphere = get_sphere(full_text)
    f = StringIO(full_text)
    reader = csv.DictReader(f, delimiter=';', quotechar='"')
    parsed_data = list(reader)

    foundGovernments = []
    notFoundFinancialYears = []
    notFoundGovernments = []
    notFoundDepartments = []
    notFoundSpheres = []
    alreadyFoundDepartments = []
    notFoundPublicEntities = []

    count = 0
    print(len(parsed_data))
    for item in parsed_data: 
        count += 1
        # Access each column by its name
        vote = item["Vote"].strip()
        department = item["Department"].strip()
        entity_name = item["EntityName"].strip()
        consol_indi = item["ConsolIndi"].strip()
        pfma = item["PFMA"].strip()
        type_ = item["Type"].strip()
        economic_classification1 = item["EconomicClassification1"].strip()
        economic_classification2 = item["EconomicClassification2"].strip()
        economic_classification3 = item["EconomicClassification3"].strip()
        economic_classification4 = item["EconomicClassification4"].strip()
        economic_classification5 = item["EconomicClassification5"].strip()
        economic_classification6 = item["EconomicClassification6"].strip()
        function_group1 = item["FunctionGroup1"].strip()
        function_group2 = item["FunctionGroup2"].strip()
        financial_year = item["FinancialYear"].strip()
        budget_phase = item["BudgetPhase"].strip()
        amount_r_thou = item["Amount (R-Thou)"].strip()
        amount = item["Amount"].strip()
        financial_year_slug = make_financial_year(financial_year)
        financialYears = FinancialYear.objects.filter(slug=financial_year_slug)

        if financialYears:
            selectedFinancialYear = financialYears.first()
            spheres = Sphere.objects.filter(
                slug="national", financial_year=selectedFinancialYear
            )

            if spheres:
                selectedSphere = spheres.first()
                governments = Government.objects.filter(sphere=selectedSphere)

                if governments:
                    selectedGovernment = governments.first()
                    foundGovernments.append(selectedGovernment)

                    departments = Department.objects.filter(
                        name=department, government=selectedGovernment
                    )
                    selectedDepartment = None

                    if departments:
                        selectedDepartment = departments.first()
                    else:
                        notFoundDepartments.append(
                            f"Department {department} for financial year {financial_year_slug} does not exist"
                        )
                        try:
                            selectedDepartment = Department.objects.create(
                                name=department,
                                government=selectedGovernment,
                                vote_number=vote,
                            )
                        except:
                            alreadyFoundDepartments.append(
                                f"Department {department} for financial year {financial_year_slug} already exists"
                            )
                    if selectedDepartment:

                        # print(
                        #     f"Public entity: {entity_name}, "
                        #     f"department: {selectedDepartment}, "
                        #     f"government: {selectedGovernment.name}, "
                        #     f"pfma: {pfma}, "
                        #     f"functiongroup1: {function_group1}, "
                        #     f"amount: {amount}"
                        # )

                        # print('before the save')

                        selectedPublicEntity, created = PublicEntity.objects.update_or_create(
                            name=entity_name,
                            department=selectedDepartment,
                            government=selectedGovernment,
                            defaults={
                                "pfma": pfma,
                                "functiongroup1": function_group1,
                                "financialYear": financial_year,
                                "amount": amount,
                                "slug": slugify(entity_name),
                            }
                        )

                        # print('Passed the save')
                        # selectedPublicEntity = None

                        # if publicEntities:
                        #     selectedPublicEntity = publicEntities.first()
                        # else:
                        #     selectedPublicEntity = PublicEntity.objects.create(
                        #         name=entity_name,
                        #         department=selectedDepartment,
                        #         government=selectedGovernment,
                        #         pfma=pfma,
                        #         functiongroup1=function_group1,
                        #         amount=amount,
                        #     )

                        if selectedPublicEntity:
                            selectedPublicEntityExpenditure = (
                                PublicEntityExpenditure.objects.create(
                                    public_entity=selectedPublicEntity,
                                    amount=amount,
                                    budget_phase=budget_phase,
                                    expenditure_type=type_,
                                    economic_classification1=economic_classification1,
                                    economic_classification2=economic_classification2,
                                    economic_classification3=economic_classification3,
                                    economic_classification4=economic_classification4,
                                    economic_classification5=economic_classification5,
                                    economic_classification6=economic_classification6,
                                    consol_indi=consol_indi,
                                )
                            )

                        else:
                            notFoundPublicEntities.append(
                                f"Public entity {entity_name} for department {department} for financial year {financial_year_slug} does not exist/not created"
                            )

                else:
                    notFoundGovernments.append(
                        f"Government for financial year {financial_year_slug} does not exist"
                    )
            else:
                notFoundSpheres.append(
                    f"National sphere for financial year {financial_year_slug} does not exist"
                )
        else:
            notFoundFinancialYears.append(
                f"Financial year {financial_year_slug} does not exist"
            )

    reportArray = notFoundFinancialYears + notFoundGovernments + notFoundGovernments + notFoundSpheres + notFoundPublicEntities
    report = ' , '.join(str(e) for e in reportArray)
    return report

class PublicEntityAdmin(admin.ModelAdmin):
    # Resource class to be used by the django-import-export package
    resource_class = PublicEntityResource

    def get_resource_kwargs(self, request, *args, **kwargs):
        """
        Get the kwargs to send on to the public entity resource when
        we import public entities.
        """
        if "sphere" in request.POST:
            return {"sphere": request.POST["sphere"]}
        return {}

    list_display = (
        "name",
        "functiongroup1",
        "department",
        "get_financial_year",
    )

    list_display_links = ("name", "functiongroup1")

    list_filter = (
        "government__sphere__financial_year__slug",
        "government__sphere__name",
        "government__name",
    )
    search_fields = (
        "government__sphere__financial_year__slug",
        "government__sphere__name",
        "government__name",
        "name",
    )
    readonly_fields = ("slug",)
    list_per_page = 20

    def get_government(self, obj):
        return obj.government.name

    def get_sphere(self, obj):
        return obj.government.sphere.name

    def get_financial_year(self, obj):
        return obj.government.sphere.financial_year.slug
    
class PublicEntitiesFileUploadAdmin(admin.ModelAdmin):
    readonly_fields = (
        "import_report",
        "user",
    )
    list_display = (
        "created_at",
        "user",
        "updated_at",
    )
    fieldsets = (
        (
            "",
            {
                "fields": (
                    "user",
                    "file",
                    "import_report",
                )
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.user = request.user
        super().save_model(request, obj, form, change)
        # It looks like the task isn't saved synchronously, so we can't set the
        # task as a related object synchronously. We have to fetch it by its ID
        # when we want to see if it's available yet.

        try:
            task_id = async_task(func=save_imported_public_entities, obj_id=obj.id)
            # If your model has a `task_id` field, persist it; otherwise skip this.
            if hasattr(obj, "task_id"):
                obj.task_id = task_id
                obj.save(update_fields=["task_id"])
        except Exception:
            # Fallback: run synchronously so admins still get a report
            report = save_imported_public_entities(obj.id)
            obj.import_report = report
            obj.save(update_fields=["import_report"])

    def processing_completed(self, obj):
        task = fetch(obj.task_id)
        if task:
            return task.success

    processing_completed.boolean = True
    processing_completed.short_description = "Processing completed"
        


admin.site.register(PublicEntityExpenditure, PublicEntityExpenditureAdmin)
admin.site.register(PublicEntity, PublicEntityAdmin)
admin.site.register(PublicEntitiesFileUpload, PublicEntitiesFileUploadAdmin)
