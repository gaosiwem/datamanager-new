from rest_framework.test import APITestCase
from django.urls import reverse
from myapp.models import InfraProject, InfraProjectSnapshot, IRMSnapshot, Sphere, FinancialYear, Quarter
from django.core.files import File
from datetime import date

class InfraProjectAPIFundingSourceTestCase(APITestCase):
    def setUp(self):
        self.url = reverse("infrastructure-project-api-list")
        self.file = open("path/to/empty/file", "rb")
        fin_year = FinancialYear.objects.create(slug="2030-31")
        sphere = Sphere.objects.create(financial_year=fin_year, name="Provincial")
        quarter = Quarter.objects.create(number=1)
        date_taken = date(year=2050, month=1, day=1)
        irm_snapshot = IRMSnapshot.objects.create(
            sphere=sphere,
            quarter=quarter,
            date_taken=date_taken,
            file=File(self.file),
        )
        project_1 = InfraProject.objects.create(IRM_project_id=1)
        InfraProjectSnapshot.objects.create(
            irm_snapshot=irm_snapshot,
            project=project_1,
            province="Eastern Cape",
            primary_funding_source="Community Library Service Grant",
            estimated_completion_date=date_taken,
        )
        project_2 = InfraProject.objects.create(IRM_project_id=2)
        InfraProjectSnapshot.objects.create(
            irm_snapshot=irm_snapshot,
            project=project_2,
            province="Free State",
            primary_funding_source="Community Library Service Grant",
            estimated_completion_date=date_taken,
        )

    def tearDown(self):
        self.file.close()
