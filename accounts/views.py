from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Count
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .decorators import role_required
from .forms import RegistrationForm
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
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        messages.success(self.request, f"Welcome back, {user.first_name or user.username}!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Invalid username or password.")
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


@role_required(User.Role.LEARNER)
def learner_dashboard(request):
    return render(request, "dashboard/learner.html")


@role_required(User.Role.INSTRUCTOR)
def instructor_dashboard(request):
    learners = User.objects.filter(role=User.Role.LEARNER, is_active=True)
    return render(request, "dashboard/instructor.html", {"learner_count": learners.count()})


@role_required(User.Role.ADMIN)
def admin_dashboard(request):
    counts = dict(User.objects.values_list("role").annotate(total=Count("id")))
    context = {
        "total_users": sum(counts.values()),
        "learner_count": counts.get(User.Role.LEARNER, 0),
        "instructor_count": counts.get(User.Role.INSTRUCTOR, 0),
        "admin_count": counts.get(User.Role.ADMIN, 0),
        "recent_users": User.objects.order_by("-date_joined")[:10],
    }
    return render(request, "dashboard/admin.html", context)
