from datetime import time as time_type

from django import forms
from django.contrib.auth import get_user_model

from bookings.models import Facility, HoursOfOperation, IceSurface, ManualReservation

User = get_user_model()
INPUT_CLASS = "input input-bordered w-full"


def _time_choices_30min():
    """Choices for 30-minute intervals: (value 'HH:MM', label '12:00 AM', ...)."""
    choices = []
    for h in range(24):
        for m in (0, 30):
            t = time_type(h, m)
            value = t.strftime("%H:%M")
            if h == 0:
                label = f"12:{m:02d} AM"
            elif h < 12:
                label = f"{h}:{m:02d} AM"
            elif h == 12:
                label = f"12:{m:02d} PM"
            else:
                label = f"{h - 12}:{m:02d} PM"
            choices.append((value, label))
    return choices


def _time_to_12h(t):
    """Return (hour_12, minute_00_or_30, 'AM'|'PM') from time. Minute rounded to 0 or 30."""
    if t is None or not hasattr(t, "hour"):
        return (12, "00", "AM")
    m = 30 if 15 <= t.minute < 45 else 0
    if t.minute >= 45:
        h24 = (t.hour + 1) % 24
        m = 0
    else:
        h24 = t.hour
    if h24 == 0:
        return (12, "30" if m == 30 else "00", "AM")
    if h24 < 12:
        return (h24, "30" if m == 30 else "00", "AM")
    if h24 == 12:
        return (12, "30" if m == 30 else "00", "PM")
    return (h24 - 12, "30" if m == 30 else "00", "PM")


def _12h_to_time(hour_12, min_str, ampm):
    """Build time from 12h hour (1-12), '00'|'30', 'AM'|'PM'."""
    h12 = int(hour_12, 10)
    m = 30 if min_str == "30" else 0
    if ampm.upper() == "AM":
        h24 = 0 if h12 == 12 else h12
    else:
        h24 = 12 if h12 == 12 else h12 + 12
    return time_type(h24 % 24, m)


class TimeSelect30Widget(forms.Select):
    """Select widget with only 30-minute interval options (no native time picker)."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=_time_choices_30min())

    def format_value(self, value):
        if value is None:
            return ""
        if hasattr(value, "hour") and hasattr(value, "minute"):
            m = value.minute
            m = 30 if 15 <= m < 45 else (0 if m < 15 else 60)
            if m == 60:
                h = (value.hour + 1) % 24
                m = 0
            else:
                h = value.hour
            return time_type(h, m).strftime("%H:%M")
        return str(value)

    def value_from_datadict(self, data, files, name):
        value = data.get(name)
        if not value:
            return None
        try:
            parts = value.strip().split(":")
            if len(parts) >= 2:
                h, m = int(parts[0], 10), int(parts[1], 10)
                m = 30 if 15 <= m < 45 else 0
                if 0 <= h <= 24 and 0 <= m < 60:
                    return time_type(h % 24, m)
        except (ValueError, TypeError):
            pass
        return None


# Short dropdowns: hour (12), minute (00/30), AM/PM (2) — max 12 options each
HOUR_12_CHOICES = [(str(i), str(i)) for i in [12] + list(range(1, 12))]
MINUTE_CHOICES = [("00", ":00"), ("30", ":30")]
AMPM_CHOICES = [("AM", "AM"), ("PM", "PM")]


class TimeSelect30CompactWidget(forms.MultiWidget):
    """Three short dropdowns: hour (12), minute (:00/:30), AM/PM."""

    def __init__(self, attrs=None):
        widgets = (
            forms.Select(attrs={"class": "select select-bordered", **(attrs or {})}, choices=HOUR_12_CHOICES),
            forms.Select(attrs={"class": "select select-bordered", **(attrs or {})}, choices=MINUTE_CHOICES),
            forms.Select(attrs={"class": "select select-bordered", **(attrs or {})}, choices=AMPM_CHOICES),
        )
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value is None:
            return [12, "00", "AM"]
        h12, m, ampm = _time_to_12h(value)
        return [str(h12), "30" if m == 30 else "00", ampm]

    def value_from_datadict(self, data, files, name):
        try:
            h = data.get(f"{name}_0", "12")
            m = data.get(f"{name}_1", "00")
            ampm = data.get(f"{name}_2", "AM")
            return _12h_to_time(h, m, ampm)
        except (ValueError, TypeError, KeyError):
            return None


class FacilityRegisterForm(forms.Form):
    """Sign up as a facility manager: create account + facility."""

    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"class": INPUT_CLASS}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": INPUT_CLASS}))
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS}),
        strip=False,
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS}),
        strip=False,
    )
    facility_name = forms.CharField(
        label="Rink / facility name",
        max_length=255,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    address_line1 = forms.CharField(
        label="Address line 1",
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "autocomplete": "address-line1",
                "placeholder": "Street address",
            }
        ),
    )
    address_line2 = forms.CharField(
        label="Address line 2 (optional)",
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "autocomplete": "address-line2",
                "placeholder": "Apt, suite, unit",
            }
        ),
    )
    city = forms.CharField(
        label="City",
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={"class": INPUT_CLASS, "autocomplete": "address-level2", "placeholder": "City"}
        ),
    )
    province = forms.CharField(
        label="Province / State",
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "autocomplete": "address-level1",
                "placeholder": "Province / State",
            }
        ),
    )
    postal_code = forms.CharField(
        label="Postal / ZIP code",
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "autocomplete": "postal-code",
                "placeholder": "Postal / ZIP code",
            }
        ),
    )

    def clean_username(self):
        if User.objects.filter(username=self.cleaned_data["username"]).exists():
            raise forms.ValidationError("A user with that username already exists.")
        return self.cleaned_data["username"]

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match.")
        return password2

    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
        )
        facility = Facility.objects.create(
            name=self.cleaned_data["facility_name"],
            address_line1=self.cleaned_data.get("address_line1", ""),
            address_line2=self.cleaned_data.get("address_line2", ""),
            city=self.cleaned_data.get("city", ""),
            province=self.cleaned_data.get("province", ""),
            postal_code=self.cleaned_data.get("postal_code", ""),
            timezone="UTC",
        )
        facility.managers.add(user)
        return user


class FacilityForm(forms.ModelForm):
    class Meta:
        model = Facility
        fields = [
            "name",
            "address_line1",
            "address_line2",
            "city",
            "province",
            "postal_code",
            "timezone",
            "handicap_accessible",
            "food_and_beverage",
            "licensed",
            "gym_weight_room",
            "change_rooms",
            "parking",
            "pro_shop",
            "wifi",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "address_line1": forms.TextInput(
                attrs={
                    "class": INPUT_CLASS,
                    "autocomplete": "address-line1",
                    "placeholder": "Street address",
                }
            ),
            "address_line2": forms.TextInput(
                attrs={
                    "class": INPUT_CLASS,
                    "autocomplete": "address-line2",
                    "placeholder": "Apt, suite, unit (optional)",
                }
            ),
            "city": forms.TextInput(
                attrs={
                    "class": INPUT_CLASS,
                    "autocomplete": "address-level2",
                    "placeholder": "City",
                }
            ),
            "province": forms.TextInput(
                attrs={
                    "class": INPUT_CLASS,
                    "autocomplete": "address-level1",
                    "placeholder": "Province / State",
                }
            ),
            "postal_code": forms.TextInput(
                attrs={
                    "class": INPUT_CLASS,
                    "autocomplete": "postal-code",
                    "placeholder": "Postal / ZIP code",
                }
            ),
            "timezone": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "handicap_accessible": forms.CheckboxInput(
                attrs={"class": "checkbox checkbox-primary"}
            ),
            "food_and_beverage": forms.CheckboxInput(attrs={"class": "checkbox checkbox-primary"}),
            "licensed": forms.CheckboxInput(attrs={"class": "checkbox checkbox-primary"}),
            "gym_weight_room": forms.CheckboxInput(attrs={"class": "checkbox checkbox-primary"}),
            "change_rooms": forms.CheckboxInput(attrs={"class": "checkbox checkbox-primary"}),
            "parking": forms.CheckboxInput(attrs={"class": "checkbox checkbox-primary"}),
            "pro_shop": forms.CheckboxInput(attrs={"class": "checkbox checkbox-primary"}),
            "wifi": forms.CheckboxInput(attrs={"class": "checkbox checkbox-primary"}),
        }


class IceSurfaceForm(forms.ModelForm):
    class Meta:
        model = IceSurface
        fields = ["name", "display_order", "default_rate"]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "display_order": forms.NumberInput(attrs={"class": INPUT_CLASS}),
            "default_rate": forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.01"}),
        }


class HoursOfOperationForm(forms.ModelForm):
    class Meta:
        model = HoursOfOperation
        fields = ["weekday", "open_time", "close_time"]
        widgets = {
            "weekday": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "open_time": TimeSelect30CompactWidget(attrs={"class": "select select-bordered"}),
            "close_time": TimeSelect30CompactWidget(attrs={"class": "select select-bordered"}),
        }


class AddHoursForm(forms.Form):
    """Add or update hours for multiple selected days with one open/close time range."""

    open_time = forms.TimeField(
        widget=TimeSelect30Widget(attrs={"class": "select select-bordered w-full", "id": "id_open_time"}),
    )
    close_time = forms.TimeField(
        widget=TimeSelect30Widget(attrs={"class": "select select-bordered w-full", "id": "id_close_time"}),
    )

    def __init__(self, *args, **kwargs):
        self.surface = kwargs.pop("surface", None)
        super().__init__(*args, **kwargs)
        for field_name, label in _bulk_hours_day_fields():
            self.fields[field_name] = forms.BooleanField(
                required=False,
                label=label,
                widget=forms.CheckboxInput(attrs={"class": "checkbox checkbox-primary add-day"}),
            )

    def clean(self):
        data = super().clean()
        open_t = data.get("open_time")
        close_t = data.get("close_time")
        any_day = any(data.get(f"day_{i}") for i in range(7))
        if any_day:
            if not open_t or not close_t:
                self.add_error(None, "Enter open and close times when days are selected.")
            elif open_t >= close_t:
                self.add_error("close_time", "Close time must be after open time.")
        else:
            self.add_error(None, "Select at least one day.")
        return data

    def save(self):
        surface = self.surface
        if not surface:
            return
        open_t = self.cleaned_data.get("open_time")
        close_t = self.cleaned_data.get("close_time")
        if not open_t or not close_t:
            return
        for i in range(7):
            if self.cleaned_data.get(f"day_{i}"):
                HoursOfOperation.objects.update_or_create(
                    ice_surface=surface,
                    weekday=i,
                    defaults={"open_time": open_t, "close_time": close_t},
                )


def _bulk_hours_day_fields():
    """Generate (field_name, label) for each weekday for BulkHoursForm."""
    for i, (_, label) in enumerate(HoursOfOperation.WEEKDAYS):
        yield (f"day_{i}", label)


class BulkHoursForm(forms.Form):
    """Set hours for multiple days at once with one open/close time range."""

    open_time = forms.TimeField(
        widget=TimeSelect30Widget(attrs={"class": "select select-bordered w-full", "id": "id_open_time"}),
    )
    close_time = forms.TimeField(
        widget=TimeSelect30Widget(attrs={"class": "select select-bordered w-full", "id": "id_close_time"}),
    )

    def __init__(self, *args, **kwargs):
        self.surface = kwargs.pop("surface", None)
        super().__init__(*args, **kwargs)
        for field_name, label in _bulk_hours_day_fields():
            self.fields[field_name] = forms.BooleanField(
                required=False,
                label=label,
                widget=forms.CheckboxInput(attrs={"class": "checkbox checkbox-primary bulk-day"}),
            )

    def clean(self):
        data = super().clean()
        open_t = data.get("open_time")
        close_t = data.get("close_time")
        any_day = any(data.get(f"day_{i}") for i in range(7))
        if any_day:
            if not open_t or not close_t:
                self.add_error(None, "Enter open and close times when days are selected.")
            elif open_t >= close_t:
                self.add_error("close_time", "Close time must be after open time.")
        return data

    def save(self):
        surface = self.surface
        if not surface:
            return
        # Remove existing hours for this surface
        HoursOfOperation.objects.filter(ice_surface=surface).delete()
        open_t = self.cleaned_data.get("open_time")
        close_t = self.cleaned_data.get("close_time")
        if not open_t or not close_t:
            return
        for i in range(7):
            if self.cleaned_data.get(f"day_{i}"):
                HoursOfOperation.objects.create(
                    ice_surface=surface,
                    weekday=i,
                    open_time=open_t,
                    close_time=close_t,
                )


class ManualReservationForm(forms.ModelForm):
    class Meta:
        model = ManualReservation
        fields = ["organization_name", "notes"]
        widgets = {
            "organization_name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "notes": forms.Textarea(
                attrs={"class": "textarea textarea-bordered w-full", "rows": 2}
            ),
        }
