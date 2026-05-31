import os
from tempfile import NamedTemporaryFile

from allauth.account.models import EmailAddress
from budgetportal.models import Department, FinancialYear, Government, Sphere
from budgetportal.tests.helpers import BaseSeleniumTestCase
from django.contrib.auth.models import User
from openpyxl import Workbook
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.wait import WebDriverWait

USERNAME = "testuser"
EMAIL = "testuser@domain.com"
PASSWORD = "12345"


class AdminDepartmentUploadTest(BaseSeleniumTestCase):
    def setUp(self):
        year = FinancialYear.objects.create(slug="2030-31")
        # spheres
        self.national_sphere = Sphere.objects.create(
            financial_year=year, name="National"
        )
        self.provincial_sphere = Sphere.objects.create(
            financial_year=year, name="Provincial"
        )
        # governments
        self.fake_national_government = Government.objects.create(
            sphere=self.national_sphere, name="South Africa"
        )
        self.fake_provincial_government = Government.objects.create(
            sphere=self.provincial_sphere, name="Free State"
        )

        user = User.objects.create_user(
            username=USERNAME,
            password=PASSWORD,
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )
        EmailAddress.objects.create(user=user, email=EMAIL, verified=True)

        self.path = os.path.dirname(__file__)

        super(AdminDepartmentUploadTest, self).setUp()

    def create_departments_xlsx(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(
            [
                "government",
                "department_name",
                "vote_number",
                "is_vote_primary",
                "combined",
                "website_url",
            ]
        )
        worksheet.append(
            [
                "South Africa",
                "The Presidency",
                1,
                True,
                (
                    "Facilitate a common programme towards\n"
                    "To serve the president in the execution of his"
                ),
                "www.thepresidency.gov.za",
            ]
        )
        worksheet.append(
            [
                "South Africa",
                "Parliament",
                2,
                True,
                (
                    "Provide the support services required by Parliament\n"
                    "These are aligned to Parliament's strategic objectives"
                ),
                "www.parliament.gov.za",
            ]
        )

        xlsx_file = NamedTemporaryFile(delete=False, suffix=".xlsx")
        xlsx_file.close()
        workbook.save(xlsx_file.name)
        return xlsx_file.name

    def test_upload_excel_for_national_sphere(self):
        filename = self.create_departments_xlsx()

        selenium = self.selenium

        # Login
        selenium.get("%s%s" % (self.live_server_url, "/admin/"))
        username = selenium.find_element_by_id("id_login")
        password = selenium.find_element_by_id("id_password")
        submit_button = selenium.find_element_by_css_selector('button[type="submit"]')
        username.send_keys(EMAIL)
        password.send_keys(PASSWORD)
        submit_button.click()

        # Navigate to departments
        selenium.find_element_by_link_text("Departments").click()

        # Navigate to departments import page
        selenium.find_element_by_link_text("IMPORT").click()

        # Fill the form values
        file_import = selenium.find_element_by_id("id_import_file")
        sphere_select = Select(selenium.find_element_by_id("id_sphere"))

        try:
            file_import.send_keys(os.path.abspath(filename))
            sphere_select.select_by_value(str(self.national_sphere.id))

            selenium.find_element_by_css_selector('input[type="submit"]').click()

            timeout = 2
            WebDriverWait(selenium, timeout).until(
                lambda driver: selenium.find_element_by_name("confirm")
            )

            selenium.find_element_by_name("confirm").click()

            timeout = 2
            WebDriverWait(selenium, timeout).until(
                lambda driver: selenium.find_element_by_class_name("success")
            )
        finally:
            os.unlink(filename)

        # Check that the departments were created

        presidency = Department.objects.get(
            government=self.fake_national_government, name="The Presidency"
        )
        self.assertEqual(presidency.vote_number, 1)
        self.assertTrue(presidency.is_vote_primary)
        self.assertIn("To serve the president", presidency.intro)
        self.assertIn("Facilitate a common", presidency.intro)
        self.assertTrue(presidency.website_url, "www.thepresidency.gov.za")

        parliament = Department.objects.get(
            government=self.fake_national_government, vote_number=2
        )
        self.assertEqual(parliament.name, "Parliament")
        self.assertTrue(parliament.is_vote_primary)
        self.assertIn("Provide the support services", parliament.intro)
        self.assertIn("These are aligned", parliament.intro)
        self.assertTrue(parliament.website_url, "www.parliament.gov.za")
