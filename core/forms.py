from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

User = get_user_model()

INPUT_CLASS = "input input-bordered w-full"


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"class": INPUT_CLASS})
        self.fields["password"].widget.attrs.update({"class": INPUT_CLASS})

    def clean_username(self):
        """Allow login with email: if the value looks like an email, resolve to username."""
        value = self.cleaned_data.get("username", "").strip()
        if value and "@" in value:
            user = User.objects.filter(email=value).first()
            if user:
                return user.username
        return value


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True, widget=forms.EmailInput(attrs={"class": "input input-bordered w-full"})
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")
        widgets = {
            "username": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "password1": forms.PasswordInput(attrs={"class": INPUT_CLASS}),
            "password2": forms.PasswordInput(attrs={"class": INPUT_CLASS}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user
