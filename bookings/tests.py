from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from bookings.models import Booking, Facility, HoursOfOperation, IceSurface, Slot
from bookings.services import (
    can_cancel_booking,
    generate_slots_for_surface,
    get_available_slots,
    release_slot,
)

User = get_user_model()


class SlotGenerationTests(TestCase):
    def setUp(self):
        self.facility = Facility.objects.create(name="Test Rink", timezone="America/Toronto")
        self.surface = IceSurface.objects.create(
            facility=self.facility,
            name="Rink A",
            default_rate=Decimal("100.00"),
        )
        HoursOfOperation.objects.create(
            ice_surface=self.surface,
            weekday=0,
            open_time=datetime.strptime("09:00", "%H:%M").time(),
            close_time=datetime.strptime("17:00", "%H:%M").time(),
        )

    def test_generate_slots_creates_slots(self):
        start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        while start.weekday() != 0:
            start += timedelta(days=1)
        end = start + timedelta(days=1)
        created = generate_slots_for_surface(self.surface, start, end)
        self.assertGreater(len(created), 0)
        self.assertEqual(Slot.objects.filter(ice_surface=self.surface).count(), len(created))

    def test_get_available_slots_returns_only_available(self):
        start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        while start.weekday() != 0:
            start += timedelta(days=1)
        end = start + timedelta(days=1)
        generate_slots_for_surface(self.surface, start, end)
        day = start.date()
        slots = get_available_slots(self.surface, day)
        self.assertTrue(all(s.state == "available" for s in slots))


class ReleaseSlotTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p", email="u@example.com")
        self.facility = Facility.objects.create(name="F", timezone="UTC")
        self.surface = IceSurface.objects.create(
            facility=self.facility, name="A", default_rate=Decimal("50")
        )
        self.slot = Slot.objects.create(
            ice_surface=self.surface,
            start=timezone.now() + timedelta(days=1),
            end=timezone.now() + timedelta(days=1, hours=1),
            rate=Decimal("50"),
            state="booked",
        )
        self.booking = Booking.objects.create(
            slot=self.slot,
            user=self.user,
            sport="hockey",
            payment_status="pending",
        )

    def test_release_slot_sets_available(self):
        release_slot(self.slot)
        self.slot.refresh_from_db()
        self.assertEqual(self.slot.state, "available")
        self.assertFalse(Booking.objects.filter(pk=self.booking.pk).exists())

    def test_can_cancel_booking_returns_true(self):
        self.assertTrue(can_cancel_booking(self.booking))
