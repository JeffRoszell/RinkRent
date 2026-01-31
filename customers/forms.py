from django import forms

from bookings.models import Booking

INPUT_CLASS = "input input-bordered w-full"


class BookingForm(forms.Form):
    """Book one or more slots: organization, sport, payment method."""

    PAYMENT_CHOICES = [
        ("pay_now", "Pay now (card)"),
        ("pay_later", "Pay when I show up"),
    ]
    organization_name = forms.CharField(
        max_length=255, required=False, widget=forms.TextInput(attrs={"class": INPUT_CLASS})
    )
    sport = forms.ChoiceField(
        choices=Booking.SPORT_CHOICES,
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
    )
    payment_method = forms.ChoiceField(
        choices=PAYMENT_CHOICES,
        initial="pay_now",
        widget=forms.RadioSelect(attrs={"class": "radio radio-primary"}),
        label="Payment",
    )
