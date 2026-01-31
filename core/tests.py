from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from bookings.models import Facility

User = get_user_model()


class AuthTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123", email="test@example.com"
        )

    def test_home_returns_200_for_anonymous(self):
        """Anonymous user gets landing page (200), not a redirect."""
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)

    def test_login_redirects_authenticated(self):
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("core:login"))
        self.assertEqual(response.status_code, 302)

    def test_login_redirects_facility_manager_to_dashboard(self):
        fm = User.objects.create_user(username="fm", password="fmpass", email="fm@example.com")
        facility = Facility.objects.create(name="Test Rink", timezone="UTC")
        facility.managers.add(fm)
        response = self.client.post(
            reverse("core:login"),
            {"username": "fm", "password": "fmpass"},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("facilities:dashboard"))

    def test_register_creates_user(self):
        response = self.client.post(
            reverse("core:register"),
            {
                "username": "newuser",
                "email": "new@example.com",
                "password1": "complexpass123!",
                "password2": "complexpass123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="newuser").exists())
