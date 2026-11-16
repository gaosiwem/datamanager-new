"""Forms for the Division of Revenue workbook preview."""

import os

from django import forms


MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MiB
ALLOWED_EXTENSIONS = {".xlsx", ".xlsm"}


class DivisionRevenueUploadForm(forms.Form):
    """Accept only reasonably-sized Excel workbooks for in-memory inspection."""

    workbook = forms.FileField(
        label="Division of Revenue workbook",
        help_text="Accepted file types: .xlsx and .xlsm (maximum 20 MB).",
    )

    def clean_workbook(self):
        workbook = self.cleaned_data["workbook"]
        extension = os.path.splitext(workbook.name)[1].lower()

        if extension not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError("Upload an .xlsx or .xlsm workbook.")
        if workbook.size > MAX_UPLOAD_SIZE:
            raise forms.ValidationError("The workbook must be no larger than 20 MB.")

        return workbook
