from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("learner/", views.learner_dashboard, name="learner_dashboard"),
    path("instructor/", views.instructor_dashboard, name="instructor_dashboard"),
    path("administrator/", views.admin_dashboard, name="admin_dashboard"),
    path("register/", views.register, name="register"),
    path("login/", views.CodemmLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
]
