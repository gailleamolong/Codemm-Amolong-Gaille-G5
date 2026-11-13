from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class RegistrationForm(UserCreationForm):
    """Sign-up form. UserCreationForm already checks that the username is unique,
    that both passwords match and that the password passes the validators."""

    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    role = forms.ChoiceField(
        choices=[
            (User.Role.LEARNER, User.Role.LEARNER.label),
            (User.Role.INSTRUCTOR, User.Role.INSTRUCTOR.label),
        ],
        initial=User.Role.LEARNER,
        help_text="Administrator accounts are created by the system administrator.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "role")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email
