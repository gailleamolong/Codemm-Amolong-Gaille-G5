from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class EmailUniqueMixin:
    """Emails are unique regardless of letter case."""

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        taken = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if taken.exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class RegistrationForm(EmailUniqueMixin, UserCreationForm):
    """Student sign-up. UserCreationForm already checks that the username is unique,
    that both passwords match and that the password passes the validators.
    New accounts are students; the administrator assigns other roles (SDD F-01)."""

    email = forms.EmailField(max_length=254)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "id_number")

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


class UserRoleForm(forms.ModelForm):
    """Used by administrators to assign a role and activate or deactivate an account."""

    class Meta:
        model = User
        fields = ("role", "is_active")
