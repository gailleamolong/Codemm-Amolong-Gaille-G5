from django.urls import path

from .views import (
    AdminDashboardView,
    HomeView,
    InstructorDashboardView,
    StudentDashboardView,
    UserRoleUpdateView,
)

urlpatterns = [
    path("", HomeView.as_view(), name="dashboard"),
    path("student/", StudentDashboardView.as_view(), name="student_dashboard"),
    path("instructor/", InstructorDashboardView.as_view(), name="instructor_dashboard"),
    path("administrator/", AdminDashboardView.as_view(), name="admin_dashboard"),
    path("administrator/users/<int:pk>/", UserRoleUpdateView.as_view(), name="user_edit"),
]
