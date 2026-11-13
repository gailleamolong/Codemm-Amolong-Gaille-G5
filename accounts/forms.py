from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User

# Autocomplete keeps password managers and autofill working.
AUTOCOMPLETE = {
    "username": "username",
    "first_name": "given-name",
    "last_name": "family-name",
    "email": "email",
    "id_number": "off",
    "password": "current-password",
    "password1": "new-password",
    "password2": "new-password",
}


def apply_hints(form):
    for name, field in form.fields.items():
        field.help_text = ""
        field.widget.attrs["autocomplete"] = AUTOCOMPLETE.get(name, "off")
    if "id_number" in form.fields:
        form.fields["id_number"].widget.attrs["placeholder"] = "e.g. 21-1234-567"
    if "password2" in form.fields:
        form.fields["password2"].label = "Confirm password"


class EmailUniqueMixin:
    """Emails are unique regardless of letter case."""

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        taken = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if taken.exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class LoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Incorrect username, email or password.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_hints(self)
        self.fields["username"].label = "Username or email"


class RegistrationForm(EmailUniqueMixin, UserCreationForm):
    """Student sign-up. UserCreationForm already checks that the username is unique,
    that both passwords match and that the password passes the validators.
    New accounts are students; the administrator assigns other roles (SDD F-01)."""

    email = forms.EmailField(max_length=254)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "id_number")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_hints(self)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.STUDENT
        if commit:
            user.save()
        return user


class ProfileForm(EmailUniqueMixin, forms.ModelForm):
    """Fields users may change on their own profile. Username and role are not editable."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "id_number")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_hints(self)


class UserRoleForm(forms.ModelForm):
    """Used by administrators to assign a role and activate or deactivate an account."""

    class Meta:
        model = User
        fields = ("role", "is_active")
