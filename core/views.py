from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView

from core.forms import LoginForm, RegisterForm

User = get_user_model()


def home(request):
    """Landing: redirect logged-in users by role, else show landing page."""
    if request.user.is_authenticated:
        try:
            from bookings.models import Facility

            if Facility.objects.filter(managers=request.user).exists():
                return redirect("facilities:dashboard")
        except Exception:
            pass
        return redirect("customers:search")
    return render(request, "core/home.html")


class Login(LoginView):
    template_name = "core/login.html"
    form_class = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        """Log in and redirect by role; use form.get_user() so we redirect the user we just authenticated."""
        auth_login(self.request, form.get_user())
        user = form.get_user()

        # Respect ?next= when present (e.g. after login_required redirect)
        redirect_to = self.get_redirect_url()
        if redirect_to:
            return HttpResponseRedirect(redirect_to)

        try:
            from bookings.models import Facility

            if Facility.objects.filter(managers=user).exists():
                return HttpResponseRedirect(reverse("facilities:dashboard"))
        except Exception:
            pass
        return HttpResponseRedirect(reverse("customers:search"))


class Logout(LogoutView):
    next_page = "core:home"


class Register(CreateView):
    form_class = RegisterForm
    template_name = "core/register.html"
    success_url = reverse_lazy("core:login")
