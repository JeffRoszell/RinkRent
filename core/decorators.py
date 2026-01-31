from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def facility_manager_required(view_func):
    """Require that the user is a manager of at least one facility."""

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        from bookings.models import Facility

        if not Facility.objects.filter(managers=request.user).exists():
            return redirect("core:home")
        return view_func(request, *args, **kwargs)

    return _wrapped
