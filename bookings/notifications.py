"""Send booking-related emails and record BookingEvent."""

from django.conf import settings
from django.core.mail import send_mail

from .models import BookingEvent


def _send_email(subject, message, to_emails, fail_silently=True):
    if not to_emails:
        return
    send_mail(
        subject,
        message,
        getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@rinkrent.example.com"),
        to_emails,
        fail_silently=fail_silently,
    )


def notify_booking_modified_by_facility(booking, message):
    """Facility edited or cancelled a booking: email customer and log event."""
    BookingEvent.objects.create(
        booking=booking,
        user=booking.user,
        event_type="facility_modified",
        message=message,
    )
    email = getattr(booking.user, "email", None)
    if email:
        _send_email(
            "Your RinkRent booking was updated",
            message,
            [email],
        )


def notify_booking_released(booking, message):
    """Facility released/cancelled the booking: email customer and log event."""
    BookingEvent.objects.create(
        booking=booking,
        user=booking.user,
        event_type="cancelled_by_facility",
        message=message,
    )
    email = getattr(booking.user, "email", None)
    if email:
        _send_email(
            "Your RinkRent booking was cancelled",
            message,
            [email],
        )


def notify_booking_created(booking):
    """Customer created a booking: optional email to facility."""
    BookingEvent.objects.create(
        booking=booking,
        user=booking.user,
        event_type="created",
        message="Booking created.",
    )
    facility = booking.slot.ice_surface.facility
    manager_emails = [m.email for m in facility.managers.all() if getattr(m, "email", None)]
    if manager_emails:
        _send_email(
            "New RinkRent booking",
            f"A new booking was made for {booking.slot.ice_surface.name} on {booking.slot.start}.",
            manager_emails,
        )


def notify_booking_cancelled_by_customer(booking):
    """Customer cancelled: optional email to facility."""
    BookingEvent.objects.create(
        booking=booking,
        user=booking.user,
        event_type="cancelled_by_customer",
        message="Customer cancelled.",
    )
    facility = booking.slot.ice_surface.facility
    manager_emails = [m.email for m in facility.managers.all() if getattr(m, "email", None)]
    if manager_emails:
        _send_email(
            "RinkRent booking cancelled",
            f"A booking for {booking.slot.ice_surface.name} on {booking.slot.start} was cancelled by the customer.",
            manager_emails,
        )
