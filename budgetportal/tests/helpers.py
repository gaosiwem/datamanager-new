"""
Common test helpers.
"""
import warnings
from datetime import datetime

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.management import call_command
from django.db import connections
from django.test import TestCase
from selenium import webdriver
from selenium.webdriver import DesiredCapabilities
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
import socket


class WagtailHackMixin:
    """
    We need to overload the LiveServerTestCase class to resolve:
    https://github.com/wagtail/wagtail/issues/1824
    """

    def _fixture_teardown(self):
        # Allow TRUNCATE ... CASCADE and don't emit the post_migrate signal
        # when flushing only a subset of the apps
        for db_name in self._databases_names(include_mirrors=False):
            # Flush the database
            inhibit_post_migrate = (
                self.available_apps is not None
                or (  # Inhibit the post_migrate signal when using serialized
                    # rollback to avoid trying to recreate the serialized data.
                    self.serialized_rollback
                    and hasattr(connections[db_name], "_test_serialized_contents")
                )
            )
            call_command(
                "flush",
                verbosity=0,
                interactive=False,
                database=db_name,
                reset_sequences=False,
                allow_cascade=True,
                inhibit_post_migrate=inhibit_post_migrate,
            )


class BaseSeleniumTestCase(WagtailHackMixin, StaticLiveServerTestCase):
    """
    Base class for Selenium tests.

    This saves a screenshot to the current directory on test failure.

    Much learned from https://github.com/marcgibbons/django-selenium-docker
    """

    host = "0.0.0.0"  # Bind to 0.0.0.0 to allow external access

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.host = socket.gethostbyname(socket.gethostname())

        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("disable-dev-shm-usage")
        d = chrome_options.to_capabilities()
        d["loggingPrefs"] = {"browser": "ALL"}
        cls.selenium = webdriver.Remote(
            command_executor="http://selenium:4444/wd/hub", desired_capabilities=d
        )
        cls.selenium.implicitly_wait(10)
        cls.wait = WebDriverWait(cls.selenium, 5)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def setUp(self):
        self.addCleanup(self.log_failure_details)

    def log_failure_details(self):
        # https://stackoverflow.com/questions/14991244/how-do-i-capture-a-screenshot-if-my-nosetests-fail
        for method, error in self._outcome.errors:
            if error:
                print(f"### collecting data for {method} {error} {self.id()}")
                for entry in self.selenium.get_log("browser"):
                    print(entry)

                now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
                if not self.selenium.get_screenshot_as_file(f"{now}-{self.id()}.png"):
                    warnings.warn("Selenium screenshot failed")

    def wait_until_text_in(self, selector, text):
        self.wait.until(
            EC.text_to_be_present_in_element((By.CSS_SELECTOR, selector), text)
        )


class WagtailHackLiveServerTestCase(WagtailHackMixin, StaticLiveServerTestCase):
    pass


class WagtailPageTestCase(TestCase):
    def breadcrumbs_test(self, response, ancestors):
        for page in ancestors:
            self.assertContains(response, page.url)
