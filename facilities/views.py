import calendar as cal_module
from datetime import date, datetime, timedelta
from itertools import groupby

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from bookings.models import Booking, Facility, HoursOfOperation, IceSurface, ManualReservation, Slot
from bookings.notifications import notify_booking_modified_by_facility, notify_booking_released
from bookings.services import ensure_slots_for_date, get_facility_tz, release_slot
from core.decorators import facility_manager_required
from facilities.forms import (
    AddHoursForm,
    BulkHoursForm,
    FacilityForm,
    FacilityRegisterForm,
    HoursOfOperationForm,
    IceSurfaceForm,
    ManualReservationForm,
)
from facilities.stripe_connect import create_account_link, get_or_create_connect_account


def _user_facility(request):
    """First facility the user manages."""
    return Facility.objects.filter(managers=request.user).first()


def facility_register(request):
    """Register as a facility manager: create account + facility. No login required."""
    if request.user.is_authenticated:
        if Facility.objects.filter(managers=request.user).exists():
            return redirect("facilities:dashboard")
        return redirect("customers:search")
    if request.method == "POST":
        form = FacilityRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request, "Your rink account is set up. Add ice surfaces and hours to get started."
            )
            return redirect("facilities:dashboard")
    else:
        form = FacilityRegisterForm()
    return render(
        request,
        "facilities/register.html",
        {"form": form, "mapbox_access_token": getattr(settings, "MAPBOX_ACCESS_TOKEN", "") or ""},
    )


@facility_manager_required
def dashboard(request):
    facility = _user_facility(request)
    if not facility:
        return redirect("core:home")
    return render(
        request,
        "facilities/dashboard.html",
        {"facility": facility},
    )


@facility_manager_required
@require_http_methods(["GET", "POST"])
def facility_edit(request):
    facility = _user_facility(request)
    if not facility:
        return redirect("core:home")
    if request.method == "POST":
        form = FacilityForm(request.POST, instance=facility)
        if form.is_valid():
            form.save()
            messages.success(request, "Facility updated.")
            return redirect("facilities:dashboard")
    else:
        form = FacilityForm(instance=facility)
    return render(
        request,
        "facilities/facility_edit.html",
        {
            "form": form,
            "facility": facility,
            "mapbox_access_token": getattr(settings, "MAPBOX_ACCESS_TOKEN", "") or "",
        },
    )


@facility_manager_required
def surface_list(request):
    facility = _user_facility(request)
    if not facility:
        return redirect("core:home")
    surfaces = facility.ice_surfaces.all()
    return render(
        request,
        "facilities/surface_list.html",
        {"facility": facility, "surfaces": surfaces},
    )


@facility_manager_required
@require_http_methods(["GET", "POST"])
def surface_create(request):
    facility = _user_facility(request)
    if not facility:
        return redirect("core:home")
    if request.method == "POST":
        form = IceSurfaceForm(request.POST)
        if form.is_valid():
            surface = form.save(commit=False)
            surface.facility = facility
            surface.save()
            messages.success(request, f"Surface {surface.name} created.")
            return redirect("facilities:surface_list")
    else:
        form = IceSurfaceForm()
    return render(request, "facilities/surface_form.html", {"form": form, "facility": facility})


@facility_manager_required
@require_http_methods(["GET", "POST"])
def surface_edit(request, pk):
    facility = _user_facility(request)
    if not facility:
        return redirect("core:home")
    surface = get_object_or_404(IceSurface, pk=pk, facility=facility)
    if request.method == "POST":
        form = IceSurfaceForm(request.POST, instance=surface)
        if form.is_valid():
            form.save()
            messages.success(request, f"Surface {surface.name} updated.")
            return redirect("facilities:surface_list")
    else:
        form = IceSurfaceForm(instance=surface)
    return render(
        request,
        "facilities/surface_form.html",
        {"form": form, "facility": facility, "surface": surface},
    )


@facility_manager_required
@require_http_methods(["GET", "POST"])
def surface_delete(request, pk):
    facility = _user_facility(request)
    if not facility:
        return redirect("core:home")
    surface = get_object_or_404(IceSurface, pk=pk, facility=facility)
    if request.method == "POST":
        name = surface.name
        surface.delete()
        messages.success(request, f"Surface {name} deleted.")
        return redirect("facilities:surface_list")
    return render(
        request,
        "facilities/surface_confirm_delete.html",
        {"facility": facility, "surface": surface},
    )


@facility_manager_required
def hours_list(request, surface_pk):
    facility = _user_facility(request)
    if not facility:
        return redirect("core:home")
    surface = get_object_or_404(IceSurface, pk=surface_pk, facility=facility)
    hours = surface.hours_of_operation.all().order_by("weekday")
    return render(
        request,
        "facilities/hours_list.html",
        {"facility": facility, "surface": surface, "hours": hours},
    )


def _bulk_hours_initial(surface):
    """Build initial dict for BulkHoursForm from surface's existing hours."""
    hours = list(surface.hours_of_operation.all().order_by("weekday"))
    initial = {}
    for i in range(7):
        initial[f"day_{i}"] = False
    if not hours:
        from datetime import time

        initial["open_time"] = time(6, 0)
        initial["close_time"] = time(22, 0)
        return initial
    first = hours[0]
    initial["open_time"] = first.open_time
    initial["close_time"] = first.close_time
    for h in hours:
        initial[f"day_{h.weekday}"] = True
    return initial


@facility_manager_required
@require_http_methods(["GET", "POST"])
def hours_bulk(request, surface_pk):
    facility = _user_facility(request)
    if not facility:
        return redirect("core:home")
    surface = get_object_or_404(IceSurface, pk=surface_pk, facility=facility)
    if request.method == "POST":
        form = BulkHoursForm(request.POST, surface=surface)
        if form.is_valid():
            form.save()
            messages.success(request, "Hours updated for selected days.")
            return redirect("facilities:hours_list", surface_pk=surface.pk)
    else:
        form = BulkHoursForm(initial=_bulk_hours_initial(surface), surface=surface)
    weekday_fields = [
        (form[f"day_{i}"], label) for i, (_, label) in enumerate(HoursOfOperation.WEEKDAYS)
    ]
    return render(
        request,
        "facilities/hours_bulk.html",
        {"form": form, "facility": facility, "surface": surface, "weekday_fields": weekday_fields},
    )


def _add_hours_initial():
    """Default initial for AddHoursForm (no days selected, 6:00–22:00)."""
    from datetime import time

    return {"open_time": time(6, 0), "close_time": time(22, 0)}


@facility_manager_required
@require_http_methods(["GET", "POST"])
def hours_create(request, surface_pk):
    facility = _user_facility(request)
    if not facility:
        return redirect("core:home")
    surface = get_object_or_404(IceSurface, pk=surface_pk, facility=facility)
    if request.method == "POST":
        form = AddHoursForm(request.POST, surface=surface)
        if form.is_valid():
            form.save()
            messages.success(request, "Hours applied to selected days.")
            return redirect("facilities:hours_list", surface_pk=surface.pk)
    else:
        form = AddHoursForm(initial=_add_hours_initial(), surface=surface)
    weekday_fields = [
        (form[f"day_{i}"], label) for i, (_, label) in enumerate(HoursOfOperation.WEEKDAYS)
    ]
    return render(
        request,
        "facilities/hours_form.html",
        {
            "form": form,
            "facility": facility,
            "surface": surface,
            "weekday_fields": weekday_fields,
            "add_flow": True,
        },
    )


@facility_manager_required
@require_http_methods(["GET", "POST"])
def hours_edit(request, surface_pk, pk):
    facility = _user_facility(request)
    if not facility:
        return redirect("core:home")
    surface = get_object_or_404(IceSurface, pk=surface_pk, facility=facility)
    h = get_object_or_404(HoursOfOperation, pk=pk, ice_surface=surface)
    if request.method == "POST":
        form = HoursOfOperationForm(request.POST, instance=h)
        if form.is_valid():
            form.save()
            messages.success(request, "Hours updated.")
            return redirect("facilities:hours_list", surface_pk=surface.pk)
    else:
        form = HoursOfOperationForm(instance=h)
    return render(
        request,
        "facilities/hours_form.html",
        {"form": form, "facility": facility, "surface": surface, "hours": h},
    )


@facility_manager_required
@require_http_methods(["GET", "POST"])
def hours_delete(request, surface_pk, pk):
    facility = _user_facility(request)
    if not facility:
        return redirect("core:home")
    surface = get_object_or_404(IceSurface, pk=surface_pk, facility=facility)
    h = get_object_or_404(HoursOfOperation, pk=pk, ice_surface=surface)
    if request.method == "POST":
        h.delete()
        messages.success(request, "Hours removed.")
        return redirect("facilities:hours_list", surface_pk=surface.pk)
    return render(
        request,
        "facilities/hours_confirm_delete.html",
        {"facility": facility, "surface": surface, "hours": h},
    )


def _week_to_range(week_str):
    """Parse 'YYYY-Www' to (sunday_date, next_sunday_date) for Sun–Sat week. Returns None if invalid."""
    if not week_str or "-W" not in week_str:
        return None
    try:
        parts = week_str.strip().split("-W")
        year = int(parts[0])
        week = int(parts[1])
        if week < 1 or week > 53:
            return None
        jan4 = date(year, 1, 4)
        monday_week1 = jan4 - timedelta(days=jan4.weekday())
        monday = monday_week1 + timedelta(weeks=week - 1)
        sunday = monday - timedelta(days=1)
        return (sunday, sunday + timedelta(days=7))
    except (ValueError, IndexError):
        return None


def _sunday_to_week_str(sunday_date):
    """Convert Sunday date to YYYY-Www (ISO week of the following Monday)."""
    monday = sunday_date + timedelta(days=1)
    jan4 = date(monday.year, 1, 4)
    monday_week1 = jan4 - timedelta(days=jan4.weekday())
    week_num = (monday - monday_week1).days // 7 + 1
    return f"{monday.year}-W{week_num:02d}"


@facility_manager_required
def slot_list(request):
    facility = _user_facility(request)
    if not facility:
        return redirect("core:home")
    surface_id_raw = request.GET.get("surface")
    surface_id = int(surface_id_raw) if surface_id_raw and surface_id_raw.isdigit() else None
    week_str = request.GET.get("week")
    state_filter = request.GET.get("state")
    tz = get_facility_tz(facility)
    surfaces = facility.ice_surfaces.all()
    slots = (
        Slot.objects.filter(ice_surface__facility=facility)
        .select_related("ice_surface", "booking", "manual_reservation")
        .order_by("start")
    )

    if surface_id:
        slots = slots.filter(ice_surface_id=surface_id)

    week_range = _week_to_range(week_str) if week_str else None
    if week_range is None:
        # Default to current week (ISO) so first load or invalid week shows this week
        today = timezone.localtime(timezone.now(), tz).date()
        jan4 = date(today.year, 1, 4)
        monday_week1 = jan4 - timedelta(days=jan4.weekday())
        week_num = (today - monday_week1).days // 7 + 1
        week_str = f"{today.year}-W{week_num:02d}"
        week_range = _week_to_range(week_str)

    if week_range:
        sunday, end_sunday = week_range
        # Ensure slots exist for each day of the week (Sun–Sat)
        if surface_id:
            surface = get_object_or_404(IceSurface, pk=surface_id, facility=facility)
            for d in range(7):
                ensure_slots_for_date(surface, sunday + timedelta(days=d))
        else:
            for d in range(7):
                day = sunday + timedelta(days=d)
                for surface in facility.ice_surfaces.all():
                    ensure_slots_for_date(surface, day)
        start_dt = timezone.make_aware(datetime.combine(sunday, datetime.min.time()), tz)
        end_dt = timezone.make_aware(datetime.combine(end_sunday, datetime.min.time()), tz)
        slots = slots.filter(start__gte=start_dt, start__lt=end_dt)

    if state_filter:
        slots = slots.filter(state=state_filter)

    slot_list_limited = list(slots[:500])

    def slot_day(s):
        return timezone.localtime(s.start, tz).date()

    slots_by_date = [(d, list(g)) for d, g in groupby(slot_list_limited, key=slot_day)]

    week_start = week_end = None
    prev_week_str = next_week_str = None
    calendar_weeks = []
    calendar_month_label = None
    if week_range:
        sunday, end_sunday = week_range
        week_start = sunday
        week_end = sunday + timedelta(days=6)
        prev_week_str = _sunday_to_week_str(sunday - timedelta(days=7))
        next_week_str = _sunday_to_week_str(sunday + timedelta(days=7))
        cal = cal_module.Calendar(cal_module.SUNDAY)
        for row_dates in cal.monthdatescalendar(week_start.year, week_start.month):
            row_sunday = row_dates[0]
            calendar_weeks.append(
                (row_dates, _sunday_to_week_str(row_sunday), row_sunday == week_start)
            )
        calendar_month_label = date(week_start.year, week_start.month, 1)

    return render(
        request,
        "facilities/slot_list.html",
        {
            "facility": facility,
            "surfaces": surfaces,
            "slots_by_date": slots_by_date,
            "surface_id": surface_id,
            "week_str": week_str or "",
            "state_filter": state_filter,
            "week_start": week_start,
            "week_end": week_end,
            "prev_week_str": prev_week_str,
            "next_week_str": next_week_str,
            "calendar_weeks": calendar_weeks,
            "calendar_month_label": calendar_month_label,
        },
    )


@facility_manager_required
@require_http_methods(["GET", "POST"])
def manual_reserve(request, slot_pk):
    facility = _user_facility(request)
    if not facility:
        return redirect("core:home")
    slot = get_object_or_404(Slot, pk=slot_pk, ice_surface__facility=facility)
    if slot.state != "available":
        messages.error(request, "That slot is not available.")
        return redirect("facilities:slot_list")
    if request.method == "POST":
        form = ManualReservationForm(request.POST)
        if form.is_valid():
            ManualReservation.objects.create(
                slot=slot,
                organization_name=form.cleaned_data["organization_name"],
                notes=form.cleaned_data.get("notes", ""),
            )
            slot.state = "manually_reserved"
            slot.save(update_fields=["state"])
            messages.success(request, "Manual reservation created.")
            return redirect("facilities:slot_list")
    else:
        form = ManualReservationForm()
    return render(
        request,
        "facilities/manual_reserve.html",
        {"facility": facility, "slot": slot, "form": form},
    )


@facility_manager_required
@require_http_methods(["POST"])
def slot_release(request, slot_pk):
    facility = _user_facility(request)
    if not facility:
        return redirect("core:home")
    slot = get_object_or_404(Slot, pk=slot_pk, ice_surface__facility=facility)
    if hasattr(slot, "booking") and slot.booking:
        notify_booking_released(
            slot.booking,
            f"Your booking for {slot.ice_surface.name} on {slot.start} was cancelled by the facility.",
        )
    release_slot(slot)
    messages.success(request, "Slot released.")
    return redirect("facilities:slot_list")


@facility_manager_required
@require_http_methods(["GET"])
def stripe_connect_start(request):
    """Redirect facility manager to Stripe Connect onboarding."""
    facility = _user_facility(request)
    if not facility:
        return redirect("core:home")
    if not settings.STRIPE_SECRET_KEY:
        messages.warning(request, "Stripe is not configured.")
        return redirect("facilities:facility_edit")
    try:
        account_id = get_or_create_connect_account(facility)
        link = create_account_link(account_id, request)
        return redirect(link.url)
    except Exception as e:
        messages.error(request, f"Could not start Stripe setup: {e}")
        return redirect("facilities:facility_edit")


@facility_manager_required
@require_http_methods(["GET", "POST"])
def booking_edit(request, booking_pk):
    facility = _user_facility(request)
    if not facility:
        return redirect("core:home")
    booking = get_object_or_404(
        Booking,
        pk=booking_pk,
        slot__ice_surface__facility=facility,
    )
    if request.method == "POST":
        org = request.POST.get("organization_name", booking.organization_name)
        sport = request.POST.get("sport", booking.sport)
        booking.organization_name = org
        booking.sport = sport
        booking.save(update_fields=["organization_name", "sport", "updated_at"])
        notify_booking_modified_by_facility(
            booking,
            f"Your booking for {booking.slot.ice_surface.name} on {booking.slot.start} was updated (organization/sport).",
        )
        messages.success(request, "Booking updated. Customer will be notified.")
        return redirect("facilities:slot_list")
    return render(
        request,
        "facilities/booking_edit.html",
        {"facility": facility, "booking": booking},
    )
