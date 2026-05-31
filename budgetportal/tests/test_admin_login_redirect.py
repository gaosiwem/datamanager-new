from django.contrib.auth.models import User
from django.test import TestCase


class AdminLoginRedirectTests(TestCase):
    def test_admin_login_redirect_uses_account_login_with_clean_next(self):
        response = self.client.get("/admin/login/?next=/admin/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/accounts/login/?next=%2Fadmin%2F")

    def test_staff_user_is_not_bounced_to_account_login(self):
        user = User.objects.create_user(
            username="staff-user",
            password="password",
            is_staff=True,
            is_active=True,
        )
        self.client.force_login(user)

        response = self.client.get("/admin/login/?next=/admin/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/admin/")
