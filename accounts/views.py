from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .decorators import role_required
from .forms import LoginForm, ProfileForm, RegistrationForm, UserRoleForm
from .models import User


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Account created for {user.username}. You can now log in.")
            return redirect("login")
        messages.error(request, "Please fix the errors below.")
    else:
        form = RegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


class CodemmLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        messages.success(self.request, f"Welcome back, {user.first_name or user.username}!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Incorrect username, email or password.")
        return super().form_invalid(form)


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("login")


@login_required
def dashboard(request):
    """Send each user to the dashboard for their role."""
    return redirect(request.user.dashboard_url_name)


@role_required(User.Role.STUDENT)
def student_dashboard(request):
    return render(request, "dashboard/student.html")


@role_required(User.Role.INSTRUCTOR)
def instructor_dashboard(request):
    return render(request, "dashboard/instructor.html")


@role_required(User.Role.ADMIN)
def admin_dashboard(request):
    users = User.objects.order_by("role", "last_name", "username")
    rows = [(u, UserRoleForm(instance=u, prefix=f"u{u.pk}")) for u in users]
    return render(request, "dashboard/admin.html", {"rows": rows})


@require_POST
@role_required(User.Role.ADMIN)
def admin_update_user(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if target == request.user or target.is_superuser:
        messages.error(request, "You can't change your own account or a superuser here.")
        return redirect("admin_dashboard")
    form = UserRoleForm(request.POST, instance=target, prefix=f"u{target.pk}")
    if form.is_valid():
        form.save()
        state = "active" if target.is_active else "deactivated"
        messages.success(request, f"{target.username} is now {target.get_role_display()} ({state}).")
    else:
        messages.error(request, f"Could not update {target.username}.")
    return redirect("admin_dashboard")


@login_required
def profile(request):
    # Always the logged-in user's own profile: there is no user id in the URL.
    return render(request, "accounts/profile.html")


@login_required
def profile_edit(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("profile")
        messages.error(request, "Please fix the errors below.")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/profile_edit.html", {"form": form})
