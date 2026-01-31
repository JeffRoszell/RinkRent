from django.urls import path

from . import stripe_webhooks, views

app_name = "customers"

urlpatterns = [
    path("", views.search, name="search"),
    path("payment/", views.payment, name="payment"),
    path("my-bookings/", views.my_bookings, name="my_bookings"),
    path("facility/<int:pk>/", views.facility_detail, name="facility_detail"),
    path(
        "facility/<int:facility_pk>/surface/<int:surface_pk>/",
        views.availability,
        name="availability",
    ),
    path("book/", views.book, name="book"),
    path("booking/<int:booking_pk>/cancel/", views.booking_cancel, name="booking_cancel"),
    path("stripe/webhook/", stripe_webhooks.stripe_webhook, name="stripe_webhook"),
]
