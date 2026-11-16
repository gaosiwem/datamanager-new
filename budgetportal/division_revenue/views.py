"""Admin view for safe Division of Revenue workbook previews."""

from django.shortcuts import render
from django_q.tasks import async_task

from .forms import DivisionRevenueUploadForm
from .parser import WorkbookValidationError, load_and_preview
from .tasks import import_division_revenue_upload
from budgetportal.models import DivisionOfRevenueUpload


def upload_view(request):
    """Validate and preview an upload without creating or changing any models."""
    preview = None
    if request.method == "POST":
        form = DivisionRevenueUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                workbook = form.cleaned_data["workbook"]
                if request.POST.get("import"):
                    upload = DivisionOfRevenueUpload.objects.create(
                        file=workbook, uploaded_by=request.user
                    )
                    upload.task_id = async_task(
                        import_division_revenue_upload,
                        upload.pk,
                        task_name="Import Division of Revenue schedules",
                    )
                    upload.save(update_fields=("task_id",))
                    preview = {
                        "filename": workbook.name,
                        "financial_year": None,
                        "status": "SUCCESS",
                        "sheet_names": [],
                        "sheet_count": 0,
                        "schedules": {},
                        "warnings": [],
                        "errors": [],
                        "queued_upload": upload,
                    }
                else:
                    preview = load_and_preview(workbook)
            except WorkbookValidationError as error:
                form.add_error("workbook", str(error))
    else:
        form = DivisionRevenueUploadForm()

    return render(
        request,
        "admin/division_revenue_upload.html",
        {"form": form, "preview": preview},
    )
