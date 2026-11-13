from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("register/", views.register, name="register"),
    path("login/", views.CodemmLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
]
