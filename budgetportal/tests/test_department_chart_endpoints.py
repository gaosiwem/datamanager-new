import json

from django.test import Client, TestCase, override_settings

from budgetportal.models import (
    Department,
    ENEData,
    EPREData,
    FinancialYear,
    Government,
    Sphere,
)


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class DepartmentChartEndpointsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.year = FinancialYear.objects.create(slug="2018-19", published=True)

        self.national = Sphere.objects.create(
            financial_year=self.year, name="National"
        )
        self.provincial = Sphere.objects.create(
            financial_year=self.year, name="Provincial"
        )

        self.south_africa = Government.objects.create(
            sphere=self.national, name="South Africa"
        )
        self.fake_cape = Government.objects.create(
            sphere=self.provincial, name="Fake Cape"
        )

        Department.objects.create(
            government=self.south_africa,
            name="The Presidency",
            vote_number=1,
            intro="",
        )
        Department.objects.create(
            government=self.fake_cape,
            name="Provincial Treasury",
            vote_number=2,
            intro="",
        )

    def create_ene(self, **overrides):
        payload = {
            "voteNumber": 1,
            "department": "The Presidency",
            "progNumber": 1,
            "programme": "Administration",
            "subprogNumber": "1",
            "subprogramme": "Executive Support",
            "economicClassification1": "Current payments",
            "economicClassification2": "Compensation of employees",
            "economicClassification3": "Salaries and wages",
            "economicClassification4": "Compensation of employees",
            "economicClassification5": "Level 5",
            "functionGroup1": "Executive and legislative organs",
            "budgetYear": "2018",
            "financialYear": "2018",
            "budgetPhase": "Main appropriation",
            "value": 100,
        }
        payload.update(overrides)
        return ENEData.objects.create(**payload)

    def create_epre(self, **overrides):
        payload = {
            "government": "Fake Cape",
            "voteNumber": 2,
            "department": "Provincial Treasury",
            "progNumber": 1,
            "programme": "Provincial Administration",
            "subprogNumber": "1",
            "subprogramme": "Provincial Support",
            "economicClassification1": "Current payments",
            "economicClassification2": "Compensation of employees",
            "economicClassification3": "Salaries and wages",
            "economicClassification4": "Compensation of employees",
            "economicClassification5": "Level 5",
            "functionGroup1": "Treasury",
            "functionGroup2": "Treasury",
            "budgetYear": "2018",
            "financialYear": "2018",
            "budgetPhase": "Main appropriation",
            "value": 100,
        }
        payload.update(overrides)
        return EPREData.objects.create(**payload)

    def test_get_programmes_returns_national_programmes_with_blank_province(self):
        self.create_ene(programme="Administration")
        self.create_ene(programme="Policy Coordination", progNumber=2, subprogNumber="2")

        response = self.client.get(
            "/get_programmes/",
            {
                "financialYear": "2018-19",
                "department": "the-presidency",
                "province": "",
                "econ": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.json()),
            ["Administration", "Policy Coordination"],
        )

    def test_get_programmes_uses_ene_for_national_econ_filter(self):
        self.create_ene(
            programme="Administration",
            economicClassification4="Goods and services",
        )
        self.create_epre(
            programme="Wrong Source",
            economicClassification4="Goods and services",
        )

        response = self.client.get(
            "/get_programmes/",
            {
                "financialYear": "2018-19",
                "department": "the-presidency",
                "province": "",
                "econ": "Goods and services",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.json()), ["Administration"])

    def test_get_programmes_returns_provincial_programmes_for_province(self):
        self.create_epre(programme="Provincial Administration")

        response = self.client.get(
            "/get_programmes/",
            {
                "financialYear": "2018-19",
                "department": "provincial-treasury",
                "province": "fake-cape",
                "econ": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.json()), ["Provincial Administration"])
