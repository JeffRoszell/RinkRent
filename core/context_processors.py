def user_has_facility(request):
    """True if the current user is a manager of any facility."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"user_has_facility": False}
    try:
        from bookings.models import Facility

        has = Facility.objects.filter(managers=request.user).exists()
    except Exception:
        has = False
    return {"user_has_facility": has}
