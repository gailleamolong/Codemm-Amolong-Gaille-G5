from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from codemm import ratelimit

from .models import User


class SignUpForm(UserCreationForm):
    """UserCreationForm checks the unique username, password strength and that both passwords match.
    Role is left out, so every sign-up is a student."""

    email = forms.EmailField()

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "username", "email", "id_number")

    def clean_email(self):
        return self.cleaned_data["email"].lower()


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "id_number")

    def clean_email(self):
        return self.cleaned_data["email"].lower()


class LoginForm(AuthenticationForm):
    MAX_FAILURES = 5
    WINDOW_SECONDS = 15 * 60
    error_messages = {**AuthenticationForm.error_messages, "invalid_login": "Incorrect username or password."}

    def clean(self):
        key = f"login:{self.data.get('username', '').lower()}:{self.request.META.get('REMOTE_ADDR', '')}"
        if ratelimit.hits(key) >= self.MAX_FAILURES:
            raise forms.ValidationError("Too many failed attempts. Try again in 15 minutes.")
        try:
            cleaned = super().clean()
        except forms.ValidationError:
            ratelimit.record(key, self.WINDOW_SECONDS)
            raise
        ratelimit.clear(key)
        return cleaned
