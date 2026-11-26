from django.urls import path

from . import views

urlpatterns = [
    path("tracks/<int:pk>/progress/", views.ProgressReportView.as_view(), name="progress_report"),
    path("tracks/<int:pk>/pass-rate/", views.PassRateReportView.as_view(), name="pass_rate_report"),
    path("my-progress/", views.MyProgressView.as_view(), name="my_progress"),
]
