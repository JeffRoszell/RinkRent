from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from bookings.models import Facility

User = get_user_model()


class FacilityAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="customer", password="pass", email="c@example.com"
        )
        self.facility = Facility.objects.create(name="Test Rink", timezone="UTC")
        self.facility.managers.add(self.user)

    def test_facility_dashboard_requires_manager(self):
        User.objects.create_user(username="other", password="pass", email="o@example.com")
        self.client.login(username="other", password="pass")
        response = self.client.get(reverse("facilities:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.client.logout()
        self.client.login(username="customer", password="pass")
        response = self.client.get(reverse("facilities:dashboard"))
        self.assertEqual(response.status_code, 200)
