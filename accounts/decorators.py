from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """Allow only logged-in users whose role is in `roles`.

    Logged-out users are sent to the login page; logged-in users with another
    role get 403 Forbidden, so typing another role's URL does not work.
    """

    def decorator(view):
        @login_required
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied("This page is not available for your role.")
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
