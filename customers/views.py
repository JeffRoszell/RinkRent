import logging
import math
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from bookings.models import Booking, Facility, IceSurface, Slot
from bookings.notifications import notify_booking_cancelled_by_customer, notify_booking_created
from bookings.services import (
    can_cancel_booking,
    get_all_slots_for_date,
    release_slot,
)
from customers.forms import BookingForm
from customers.stripe_payment import create_booking_payment_intent, refund_booking


def _approx_km(lat1, lng1, lat2, lng2):
    """Rough distance in km (equirectangular approximation)."""
    R = 6371  # Earth radius km
    dlat = math.radians(float(lat2) - float(lat1))
    dlng = math.radians(float(lng2) - float(lng1))
    x = dlng * math.cos(math.radians((float(lat1) + float(lat2)) / 2))
    return R * math.sqrt(dlat * dlat + x * x)


def search(request):
    """List facilities; optional sort by distance if lat/lng provided."""
    try:
        lat = float(request.GET.get("lat")) if request.GET.get("lat") is not None else None
    except (ValueError, TypeError):
        lat = None
    try:
        lng = float(request.GET.get("lng")) if request.GET.get("lng") is not None else None
    except (ValueError, TypeError):
        lng = None
    facilities = Facility.objects.prefetch_related(
        "ice_surfaces", "ice_surfaces__hours_of_operation"
    ).all()

    facility_list = []
    if lat is not None and lng is not None:

        def dist_key(item):
            f, d = item
            return d if d is not None else float("inf")

        for f in facilities:
            if f.latitude is not None and f.longitude is not None:
                km = round(_approx_km(lat, lng, f.latitude, f.longitude), 1)
                facility_list.append((f, km))
            else:
                facility_list.append((f, None))
        facility_list.sort(key=dist_key)
    else:
        facility_list = [(f, None) for f in facilities]

    return render(
        request,
        "customers/search.html",
        {"facility_list": facility_list, "lat": lat, "lng": lng},
    )


def facility_detail(request, pk):
    """Show facility: surface dropdown + date, then grid of slots (available clickable, taken shown)."""
    facility = get_object_or_404(Facility, pk=pk)
    surfaces = facility.ice_surfaces.all()
    today = timezone.now().date()
    min_date = today.isoformat()
    surface_id_raw = request.GET.get("surface")
    date_str = request.GET.get("date")
    surface = None
    all_slots = []

    if surface_id_raw and date_str:
        try:
            surface_id = int(surface_id_raw)
            surface = get_object_or_404(IceSurface, pk=surface_id, facility=facility)
            day = datetime.strptime(date_str, "%Y-%m-%d").date()
            all_slots = get_all_slots_for_date(surface, day)
        except (ValueError, TypeError):
            pass

    return render(
        request,
        "customers/facility_detail.html",
        {
            "facility": facility,
            "surfaces": surfaces,
            "surface": surface,
            "all_slots": all_slots,
            "date_str": date_str or "",
            "min_date": min_date,
        },
    )


def availability(request, facility_pk, surface_pk):
    """Legacy: redirect to facility_detail with surface and date in query params."""
    date_str = request.GET.get("date", "")
    url = reverse("customers:facility_detail", kwargs={"pk": facility_pk})
    if date_str:
        url += "?surface=" + str(surface_pk) + "&date=" + date_str
    return redirect(url)


@login_required
@require_http_methods(["GET", "POST"])
def book(request):
    """Book selected slot(s): POST with slot ids, organization, sport. Creates Booking(s); payment in step 6."""
    slot_ids = request.GET.getlist("slot") or request.POST.getlist("slot")
    if not slot_ids:
        return redirect("customers:search")
    slots = (
        Slot.objects.filter(
            pk__in=slot_ids,
            state="available",
        )
        .select_related("ice_surface", "ice_surface__facility")
        .order_by("start")
    )
    if not slots:
        return render(
            request, "customers/book_error.html", {"message": "No valid available slots selected."}
        )
    facility = slots[0].ice_surface.facility
    for s in slots:
        if s.ice_surface.facility_id != facility.pk or s.state != "available":
            return render(
                request,
                "customers/book_error.html",
                {"message": "Slots are invalid or no longer available."},
            )

    if request.method == "POST":
        form = BookingForm(request.POST)
        if form.is_valid():
            slot_ids = [s.pk for s in slots]
            slots_recheck = (
                Slot.objects.filter(pk__in=slot_ids, state="available")
                .select_related("ice_surface", "ice_surface__facility")
                .order_by("start")
            )
            if slots_recheck.count() != len(slot_ids):
                return render(
                    request,
                    "customers/book_error.html",
                    {"message": "One or more slots are no longer available. Please choose again."},
                )
            slots = list(slots_recheck)
            total = sum(s.rate for s in slots)
            total_cents = int(total * 100)
            bookings_created = []
            pay_now = form.cleaned_data.get("payment_method") == "pay_now"

            for slot in slots:
                booking = Booking.objects.create(
                    slot=slot,
                    user=request.user,
                    organization_name=form.cleaned_data.get("organization_name", ""),
                    sport=form.cleaned_data["sport"],
                    amount_paid=slot.rate,
                    payment_status="pending",
                )
                slot.state = "booked"
                slot.save(update_fields=["state"])
                bookings_created.append(booking)
                notify_booking_created(booking)

            stripe_secret = (getattr(settings, "STRIPE_SECRET_KEY", None) or "").strip()
            stripe_publishable = (getattr(settings, "STRIPE_PUBLISHABLE_KEY", None) or "").strip()

            if pay_now and total_cents > 0:
                if not stripe_secret or not stripe_publishable:
                    messages.warning(
                        request,
                        "Booking confirmed. Stripe keys are not set in server config; please pay at the rink.",
                    )
                elif not facility.stripe_account_id:
                    messages.warning(
                        request,
                        "Booking confirmed. This facility has not connected Stripe for online payments; please pay at the rink.",
                    )
                else:
                    try:
                        result = create_booking_payment_intent(
                            total_cents,
                            facility,
                            [b.pk for b in bookings_created],
                            metadata={"booking_ids": ",".join(str(b.pk) for b in bookings_created)},
                        )
                        for b in bookings_created:
                            b.stripe_payment_intent_id = result["payment_intent_id"]
                            b.save(update_fields=["stripe_payment_intent_id"])
                        request.session["payment_client_secret"] = result["client_secret"]
                        request.session.modified = True
                        return redirect("customers:payment")
                    except Exception as e:
                        logging.exception("Stripe PaymentIntent failed: %s", e)
                        messages.warning(
                            request,
                            "Booking confirmed. Payment could not be started (%s); please pay at the rink.",
                            str(e)[:80],
                        )
            elif pay_now:
                messages.info(request, "Booking confirmed. Pay at the rink when you arrive.")
            return redirect("customers:my_bookings")
    else:
        form = BookingForm()
    total = sum(s.rate for s in slots)
    can_pay_now = bool(
        facility.stripe_account_id
        and getattr(settings, "STRIPE_SECRET_KEY", None)
        and getattr(settings, "STRIPE_PUBLISHABLE_KEY", None)
        and total > 0
    )
    if not can_pay_now and form.fields["payment_method"].initial == "pay_now":
        form.initial["payment_method"] = "pay_later"
    return render(
        request,
        "customers/book_confirm.html",
        {
            "facility": facility,
            "slots": slots,
            "form": form,
            "total": total,
            "can_pay_now": can_pay_now,
        },
    )


@login_required
def payment(request):
    """Stripe payment page: confirm PaymentIntent with client_secret from session."""
    client_secret = request.session.pop("payment_client_secret", None)
    publishable_key = getattr(settings, "STRIPE_PUBLISHABLE_KEY", "") or ""
    if not client_secret or not publishable_key:
        if not client_secret:
            messages.warning(
                request, "Payment session expired. Your booking is confirmed—see My bookings."
            )
        return redirect("customers:my_bookings")
    return render(
        request,
        "customers/payment.html",
        {
            "client_secret": client_secret,
            "stripe_publishable_key": publishable_key,
        },
    )


@login_required
def my_bookings(request):
    """List current user's upcoming and past bookings."""
    now = timezone.now()
    bookings = (
        Booking.objects.filter(user=request.user)
        .select_related("slot", "slot__ice_surface", "slot__ice_surface__facility")
        .order_by("-slot__start")
    )
    upcoming = [b for b in bookings if b.slot.start >= now]
    past = [b for b in bookings if b.slot.start < now]
    return render(
        request,
        "customers/my_bookings.html",
        {"upcoming": upcoming, "past": past},
    )


@login_required
@require_http_methods(["POST"])
def booking_cancel(request, booking_pk):
    """Cancel a booking (release slot). Only allowed for own booking and if can_cancel."""
    booking = get_object_or_404(Booking, pk=booking_pk, user=request.user)
    if not can_cancel_booking(booking):
        return redirect("customers:my_bookings")
    notify_booking_cancelled_by_customer(booking)
    if booking.payment_status == "paid" and booking.stripe_payment_intent_id:
        refund_booking(booking)
    release_slot(booking.slot)
    return redirect("customers:my_bookings")
