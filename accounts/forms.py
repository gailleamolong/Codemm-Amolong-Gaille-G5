from django import forms
from django.contrib.auth.forms import UserCreationForm

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
