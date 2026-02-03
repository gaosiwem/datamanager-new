from django.contrib import admin, messages

from data_validation.models import ValidationRun, ValidationResult
from data_validation.services.extract_data import get_external_data
from data_validation.services.validate import run_validation

# Register your models here.
@admin.register(ValidationRun)
class ValidationRunAdmin(admin.ModelAdmin):
    list_display = ("document_type", "financial_year", "status", "created_at")
    readonly_fields = ("status", "created_at")

    def save_model(self, request, obj, form, change):
        # is_new = obj.pk is None
        super().save_model(request, obj, form, change)        
        try:
            
            external_data = get_external_data(
                file_path= obj.source_file.path, financialYear=obj.financial_year.slug, document_type=obj.document_type)
            run_validation(obj, external_data)
            obj.status = "completed"
            obj.save(update_fields=["status"])

            self.message_user(request, "Validation completed successfully.", level=messages.SUCCESS)
        
        except Exception as e:
            print(e.__class__.__name__, e)
            obj.status = "failed"
            obj.save(update_fields=["status"])
            self.message_user(request, str(e), messages.ERROR)


@admin.register(ValidationResult)
class ValidationResultAdmin(admin.ModelAdmin):
    list_display = (
        "financial_year",
        "document_type",
        'province',
        "department",
        "programme",
        "subprogramme",
        "internal_amount",
        "external_amount",
        "is_valid",
    )

    list_filter = (
        "is_valid",
        "validation_run__financial_year",
        "validation_run__document_type",
        'province',
        'department'
    )

    search_fields = (
        "department",
        "programme",
        "subprogramme",
        "validation_run__financial_year",
        "validation_run__document_type",
        'province',
        'department'
    )

    def financial_year(self, obj):
        return obj.validation_run.financial_year
    financial_year.short_description = "Financial year"
    financial_year.admin_order_field = "validation_run__financial_year"

    def document_type(self, obj):
        return obj.validation_run.document_type
    document_type.short_description = "Document type"
    document_type.admin_order_field = "validation_run__document_type"

    


