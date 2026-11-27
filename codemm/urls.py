from django.contrib import admin
from django.contrib.auth.views import LoginView
from django.urls import include, path

from accounts.forms import LoginForm

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("accounts/login/", LoginView.as_view(authentication_form=LoginForm), name="login"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("tracks/", include("tracks.urls")),
    path("reviews/", include("reviews.urls")),
    path("reports/", include("reports.urls")),
    path("", include("dashboard.urls")),
]
