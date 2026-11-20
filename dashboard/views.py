from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, TemplateView, UpdateView

from accounts.models import User

DASHBOARDS = {
    User.Role.ADMIN: "admin_dashboard",
    User.Role.INSTRUCTOR: "instructor_dashboard",
    User.Role.STUDENT: "student_dashboard",
}


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    role = None

    def test_func(self):
        return self.request.user.role == self.role


class HomeView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return redirect(DASHBOARDS[request.user.role])


class StudentDashboardView(RoleRequiredMixin, TemplateView):
    role = User.Role.STUDENT
    template_name = "dashboard/student.html"


class InstructorDashboardView(RoleRequiredMixin, TemplateView):
    role = User.Role.INSTRUCTOR
    template_name = "dashboard/instructor.html"


class AdminDashboardView(RoleRequiredMixin, ListView):
    role = User.Role.ADMIN
    template_name = "dashboard/admin.html"
    queryset = User.objects.order_by("role", "last_name", "username")
    context_object_name = "users"


class UserRoleUpdateView(RoleRequiredMixin, SuccessMessageMixin, UpdateView):
    role = User.Role.ADMIN
    template_name = "dashboard/user_edit.html"
    fields = ("role", "is_active")
    success_url = reverse_lazy("admin_dashboard")
    success_message = "%(username)s updated."

    def get_queryset(self):
        return User.objects.exclude(pk=self.request.user.pk).exclude(is_superuser=True)

    def get_success_message(self, cleaned_data):
        return self.success_message % {"username": self.object.username}
