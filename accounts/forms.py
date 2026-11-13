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


class ProfileForm(forms.ModelForm):
    """Fields a user may change on their own profile. Username and role are not editable."""

    contact_number = forms.RegexField(
        regex=r"^\+?[0-9][0-9 \-]{6,18}$",
        required=False,
        max_length=20,
        help_text="Optional. Digits, spaces or dashes, e.g. 0917 123 4567.",
        error_messages={"invalid": "Enter a valid contact number."},
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "contact_number")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        taken = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if taken.exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email
