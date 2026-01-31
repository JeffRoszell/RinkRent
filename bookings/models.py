from decimal import Decimal

from django.conf import settings
from django.db import models


class Facility(models.Model):
    """A rink/facility that has one or more ice surfaces."""

    name = models.CharField(max_length=255)
    address = models.TextField(blank=True)  # legacy / fallback; prefer structured fields
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    timezone = models.CharField(max_length=63, default="UTC")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    stripe_account_id = models.CharField(
        max_length=255, blank=True, help_text="Stripe Connect account for payouts"
    )
    # Amenities / what the facility offers (shown to customers)
    handicap_accessible = models.BooleanField(default=False, verbose_name="Handicap accessible")
    food_and_beverage = models.BooleanField(default=False, verbose_name="Food & beverage")
    licensed = models.BooleanField(default=False, verbose_name="Licensed (alcohol)")
    gym_weight_room = models.BooleanField(default=False, verbose_name="Gym / weight room")
    change_rooms = models.BooleanField(default=False, verbose_name="Change rooms")
    parking = models.BooleanField(default=False, verbose_name="Parking")
    pro_shop = models.BooleanField(default=False, verbose_name="Pro shop")
    wifi = models.BooleanField(default=False, verbose_name="Wi‑Fi")
    managers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="managed_facilities",
        blank=True,
        help_text="Users who can manage this facility",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Facilities"

    def __str__(self):
        return self.name

    def get_full_address(self):
        """Single-line address from structured fields; falls back to legacy address."""
        parts = [self.address_line1, self.address_line2, self.city, self.province, self.postal_code]
        line = ", ".join(p for p in parts if p).strip()
        return line or self.address or ""

    get_full_address.short_description = "Address"

    # Amenity field names and display labels for templates
    AMENITY_FIELDS = [
        ("handicap_accessible", "Handicap accessible"),
        ("food_and_beverage", "Food & beverage"),
        ("licensed", "Licensed"),
        ("gym_weight_room", "Gym / weight room"),
        ("change_rooms", "Change rooms"),
        ("parking", "Parking"),
        ("pro_shop", "Pro shop"),
        ("wifi", "Wi‑Fi"),
    ]

    def get_amenities_list(self):
        """Return list of amenity labels that are True for this facility."""
        return [
            label for field_name, label in self.AMENITY_FIELDS if getattr(self, field_name, False)
        ]


class IceSurface(models.Model):
    """A single ice surface (e.g. Rink A) within a facility."""

    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="ice_surfaces")
    name = models.CharField(max_length=255)
    display_order = models.PositiveSmallIntegerField(default=0)
    default_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Default price per 1-hour slot in dollars",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return f"{self.facility.name} – {self.name}"


class HoursOfOperation(models.Model):
    """Open/close times per weekday for an ice surface."""

    WEEKDAYS = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]
    ice_surface = models.ForeignKey(
        IceSurface, on_delete=models.CASCADE, related_name="hours_of_operation"
    )
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS)
    open_time = models.TimeField()
    close_time = models.TimeField()

    class Meta:
        ordering = ["weekday"]
        unique_together = [["ice_surface", "weekday"]]

    def __str__(self):
        return (
            f"{self.ice_surface} – {self.get_weekday_display()} {self.open_time}-{self.close_time}"
        )


class Slot(models.Model):
    """A 1-hour bookable time slot for an ice surface."""

    STATE_CHOICES = [
        ("available", "Available"),
        ("booked", "Booked"),
        ("blocked", "Blocked"),
        ("manually_reserved", "Manually reserved"),
    ]
    ice_surface = models.ForeignKey(IceSurface, on_delete=models.CASCADE, related_name="slots")
    start = models.DateTimeField()
    end = models.DateTimeField()
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default="available")

    class Meta:
        ordering = ["start"]
        unique_together = [["ice_surface", "start"]]

    def __str__(self):
        return f"{self.ice_surface} {self.start} ({self.state})"


class Booking(models.Model):
    """A customer booking for one or more slots (one Booking per Slot; multiple for multi-hour)."""

    SPORT_CHOICES = [
        ("hockey", "Hockey"),
        ("ringette", "Ringette"),
        ("other", "Other"),
    ]
    slot = models.OneToOneField(Slot, on_delete=models.CASCADE, related_name="booking")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings"
    )
    organization_name = models.CharField(max_length=255, blank=True)
    sport = models.CharField(max_length=20, choices=SPORT_CHOICES, default="hockey")
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_status = models.CharField(
        max_length=20, default="pending"
    )  # pending, paid, refunded, failed
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} – {self.slot}"


class ManualReservation(models.Model):
    """Phone/walk-in reservation (no customer account)."""

    slot = models.OneToOneField(Slot, on_delete=models.CASCADE, related_name="manual_reservation")
    organization_name = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.organization_name} – {self.slot}"


class BookingEvent(models.Model):
    """Log of booking-related events for notifications and audit."""

    booking = models.ForeignKey(
        Booking, on_delete=models.SET_NULL, related_name="events", null=True, blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )
    event_type = models.CharField(
        max_length=50
    )  # e.g. created, updated, cancelled, facility_modified
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_type} @ {self.created_at}"
