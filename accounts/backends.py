from django.contrib.auth.backends import ModelBackend

from .models import User


class UsernameOrEmailBackend(ModelBackend):
    """Log in with either the username or the email address."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username and "@" in username:
            match = User.objects.filter(email__iexact=username.strip()).values_list("username", flat=True).first()
            if match:
                username = match
        return super().authenticate(request, username=username, password=password, **kwargs)
