from django import forms
from budgetportal import models

class InfrastructureImportAdminForm(forms.form):
    file = forms.FileField(
        required=True,
        help_text="Upload a .csv or .xlsx file containing infrastructure projects."
    )