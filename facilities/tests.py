from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from bookings.models import Facility, HoursOfOperation, IceSurface

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


class AddHoursTests(TestCase):
    """Add hours of operation with multiple days selected."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="manager", password="pass", email="m@example.com"
        )
        self.facility = Facility.objects.create(name="Maple Leaf Arena", timezone="America/Toronto")
        self.facility.managers.add(self.user)
        self.surface = IceSurface.objects.create(
            facility=self.facility, name="Main ice", display_order=0
        )

    def test_add_hours_applies_to_selected_days_only(self):
        self.client.login(username="manager", password="pass")
        url = reverse("facilities:hours_create", kwargs={"surface_pk": self.surface.pk})
        get_resp = self.client.get(url)
        csrf = get_resp.cookies.get("csrftoken")
        csrf_token = csrf.value if csrf else ""
        # Apply 6:00–22:00 to Monday (0), Wednesday (2), Friday (4)
        response = self.client.post(
            url,
            {
                "csrfmiddlewaretoken": csrf_token,
                "day_0": "on",
                "day_2": "on",
                "day_4": "on",
                "open_time": "06:00",
                "close_time": "22:00",
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        hours = list(
            HoursOfOperation.objects.filter(ice_surface=self.surface).order_by("weekday")
        )
        self.assertEqual(len(hours), 3)
        weekdays = [h.weekday for h in hours]
        self.assertEqual(weekdays, [0, 2, 4])
        for h in hours:
            self.assertEqual(h.open_time.strftime("%H:%M"), "06:00")
            self.assertEqual(h.close_time.strftime("%H:%M"), "22:00")
