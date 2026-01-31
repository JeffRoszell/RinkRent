from django.urls import path

from . import views

app_name = "facilities"

urlpatterns = [
    path("register/", views.facility_register, name="register"),
    path("", views.dashboard, name="dashboard"),
    path("edit/", views.facility_edit, name="facility_edit"),
    path("stripe/connect/", views.stripe_connect_start, name="stripe_connect_start"),
    path("surfaces/", views.surface_list, name="surface_list"),
    path("surfaces/new/", views.surface_create, name="surface_create"),
    path("surfaces/<int:pk>/edit/", views.surface_edit, name="surface_edit"),
    path("surfaces/<int:pk>/delete/", views.surface_delete, name="surface_delete"),
    path("surfaces/<int:surface_pk>/hours/", views.hours_list, name="hours_list"),
    path("surfaces/<int:surface_pk>/hours/set-weekly/", views.hours_bulk, name="hours_bulk"),
    path("surfaces/<int:surface_pk>/hours/new/", views.hours_create, name="hours_create"),
    path("surfaces/<int:surface_pk>/hours/<int:pk>/edit/", views.hours_edit, name="hours_edit"),
    path(
        "surfaces/<int:surface_pk>/hours/<int:pk>/delete/", views.hours_delete, name="hours_delete"
    ),
    path("slots/", views.slot_list, name="slot_list"),
    path("slots/<int:slot_pk>/manual/", views.manual_reserve, name="manual_reserve"),
    path("slots/<int:slot_pk>/release/", views.slot_release, name="slot_release"),
    path("bookings/<int:booking_pk>/edit/", views.booking_edit, name="booking_edit"),
]
