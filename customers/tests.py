from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking, Facility, IceSurface, Slot

User = get_user_model()


class SearchTests(TestCase):
    def setUp(self):
        self.client = Client()
        Facility.objects.create(name="Rink One", timezone="UTC")
        Facility.objects.create(name="Rink Two", timezone="UTC")

    def test_search_returns_200(self):
        response = self.client.get(reverse("customers:search"))
        self.assertEqual(response.status_code, 200)

    def test_search_lists_facilities(self):
        response = self.client.get(reverse("customers:search"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rink One")
        self.assertContains(response, "Rink Two")


class BookingFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="booker", password="pass", email="b@example.com"
        )
        self.facility = Facility.objects.create(name="F", timezone="UTC")
        self.surface = IceSurface.objects.create(
            facility=self.facility, name="A", default_rate=Decimal("75")
        )
        self.slot = Slot.objects.create(
            ice_surface=self.surface,
            start=timezone.now() + timedelta(days=1),
            end=timezone.now() + timedelta(days=1, hours=1),
            rate=Decimal("75"),
            state="available",
        )

    def test_book_requires_login(self):
        response = self.client.post(
            reverse("customers:book") + f"?slot={self.slot.pk}",
            {"organization_name": "Team", "sport": "hockey", "payment_method": "pay_later"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_book_get_shows_confirmation_form(self):
        """GET with valid slot shows confirmation page (200); no booking created yet."""
        self.client.login(username="booker", password="pass")
        response = self.client.get(reverse("customers:book") + f"?slot={self.slot.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirm booking")
        self.assertFalse(Booking.objects.filter(slot=self.slot).exists())
        self.slot.refresh_from_db()
        self.assertEqual(self.slot.state, "available")

    def test_book_creates_booking_when_logged_in(self):
        """POST with valid form creates booking and redirects (e.g. to my_bookings)."""
        self.client.login(username="booker", password="pass")
        response = self.client.post(
            reverse("customers:book") + f"?slot={self.slot.pk}",
            {
                "organization_name": "Team",
                "sport": "hockey",
                "payment_method": "pay_later",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Booking.objects.filter(user=self.user, slot=self.slot).exists())
        self.slot.refresh_from_db()
        self.assertEqual(self.slot.state, "booked")

    def test_book_without_slot_redirects_to_search(self):
        """GET or POST to book with no slot redirects to search."""
        self.client.login(username="booker", password="pass")
        response = self.client.get(reverse("customers:book"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("customers:search"))

    def test_book_with_unavailable_slot_shows_error(self):
        """POST with a slot that was taken in the meantime shows error page (200)."""
        self.slot.state = "booked"
        self.slot.save(update_fields=["state"])
        self.client.login(username="booker", password="pass")
        response = self.client.post(
            reverse("customers:book") + f"?slot={self.slot.pk}",
            {
                "organization_name": "Team",
                "sport": "hockey",
                "payment_method": "pay_later",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No valid available slots")
        self.assertFalse(Booking.objects.filter(slot=self.slot).exists())
