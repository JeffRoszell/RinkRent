"""
Booking business logic: slot generation, availability, cancel checks.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone

from .models import Slot


def get_facility_tz(facility):
    """Return the facility's timezone for date/slot logic. Use for filtering slots by date."""
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(facility.timezone or "UTC")
    except Exception:
        return timezone.get_current_timezone()


def _facility_tz(facility):
    return get_facility_tz(facility)


def generate_slots_for_surface(ice_surface, start_date, end_date):
    """
    Generate 1-hour slots for an ice surface between start_date and end_date
    based on its hours of operation. Creates only slots that don't already exist.
    """
    created = []
    day = start_date.date() if hasattr(start_date, "date") else start_date
    end = end_date.date() if hasattr(end_date, "date") else end_date
    hours = {h.weekday: (h.open_time, h.close_time) for h in ice_surface.hours_of_operation.all()}
    tz = _facility_tz(ice_surface.facility)
    rate = ice_surface.default_rate or Decimal("0")

    while day <= end:
        if day.weekday() not in hours:
            day += timedelta(days=1)
            continue
        open_t, close_t = hours[day.weekday()]
        slot_start = timezone.make_aware(datetime.combine(day, open_t), tz)
        day_end_dt = timezone.make_aware(datetime.combine(day, close_t), tz)

        while slot_start + timedelta(hours=1) <= day_end_dt:
            slot_end = slot_start + timedelta(hours=1)
            _, was_created = Slot.objects.get_or_create(
                ice_surface=ice_surface,
                start=slot_start,
                defaults={"end": slot_end, "rate": rate, "state": "available"},
            )
            if was_created:
                created.append((slot_start, slot_end))
            slot_start = slot_end

        day += timedelta(days=1)

    return created


def ensure_slots_for_date(ice_surface, date):
    """
    Generate slots for this surface on the given date if hours exist for that weekday
    and no slots exist yet. Call before get_available_slots so availability "just works"
    without requiring the user to run generate_slots.
    """
    tz = _facility_tz(ice_surface.facility)
    start = timezone.make_aware(datetime.combine(date, datetime.min.time()), tz)
    end = start + timedelta(days=1)  # end of requested day
    existing = Slot.objects.filter(
        ice_surface=ice_surface,
        start__gte=start,
        start__lt=end,
    ).exists()
    if not existing:
        generate_slots_for_surface(ice_surface, start, end - timedelta(seconds=1))


def get_available_slots(ice_surface, date):
    """Return slots that are available (state=available) for the given surface and date."""
    ensure_slots_for_date(ice_surface, date)
    tz = _facility_tz(ice_surface.facility)
    start = timezone.make_aware(datetime.combine(date, datetime.min.time()), tz)
    end = start + timedelta(days=1)
    return Slot.objects.filter(
        ice_surface=ice_surface,
        start__gte=start,
        start__lt=end,
        state="available",
    ).order_by("start")


def get_all_slots_for_date(ice_surface, date):
    """Return all slots (available and taken) for the given surface and date, for display."""
    ensure_slots_for_date(ice_surface, date)
    tz = _facility_tz(ice_surface.facility)
    start = timezone.make_aware(datetime.combine(date, datetime.min.time()), tz)
    end = start + timedelta(days=1)
    return (
        Slot.objects.filter(
            ice_surface=ice_surface,
            start__gte=start,
            start__lt=end,
        )
        .select_related("booking", "manual_reservation")
        .order_by("start")
    )


def can_cancel_booking(booking):
    """
    Customer can cancel if it doesn't interfere with adjacent slots.
    For a single-slot booking, we only need to ensure we're not breaking a multi-slot
    group. For now: allow cancel if the slot is the only one for this user at this
    facility at this time (no adjacent same-user booking). Simplification: always allow
    cancel; we can add "adjacent same booking group" check later.
    """
    return True


def release_slot(slot):
    """Release a slot (remove booking or manual reservation, set state to available)."""
    if hasattr(slot, "booking") and slot.booking:
        slot.booking.delete()
    if hasattr(slot, "manual_reservation") and slot.manual_reservation:
        slot.manual_reservation.delete()
    slot.state = "available"
    slot.save(update_fields=["state"])
