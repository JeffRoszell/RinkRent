from django.contrib import admin

from .models import (
    Booking,
    BookingEvent,
    Facility,
    HoursOfOperation,
    IceSurface,
    ManualReservation,
    Slot,
)


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ["name", "get_full_address", "timezone"]
    filter_horizontal = ["managers"]
    list_filter = ["handicap_accessible", "parking", "food_and_beverage"]
    fieldsets = (
        (None, {"fields": ("name", "managers", "timezone", "stripe_account_id")}),
        (
            "Address",
            {
                "fields": (
                    "address",
                    "address_line1",
                    "address_line2",
                    "city",
                    "province",
                    "postal_code",
                    "latitude",
                    "longitude",
                )
            },
        ),
        (
            "Amenities",
            {
                "fields": (
                    "handicap_accessible",
                    "food_and_beverage",
                    "licensed",
                    "gym_weight_room",
                    "change_rooms",
                    "parking",
                    "pro_shop",
                    "wifi",
                )
            },
        ),
    )


@admin.register(IceSurface)
class IceSurfaceAdmin(admin.ModelAdmin):
    list_display = ["name", "facility", "display_order", "default_rate"]


@admin.register(HoursOfOperation)
class HoursOfOperationAdmin(admin.ModelAdmin):
    list_display = ["ice_surface", "weekday", "open_time", "close_time"]


@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin):
    list_display = ["ice_surface", "start", "end", "rate", "state"]
    list_filter = ["state", "ice_surface"]


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["slot", "user", "organization_name", "sport", "payment_status"]


@admin.register(ManualReservation)
class ManualReservationAdmin(admin.ModelAdmin):
    list_display = ["slot", "organization_name", "created_at"]


@admin.register(BookingEvent)
class BookingEventAdmin(admin.ModelAdmin):
    list_display = ["booking", "event_type", "user", "created_at"]
