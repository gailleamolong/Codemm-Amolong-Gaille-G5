from django.urls import path

from . import student_views, views

urlpatterns = [
    path("", views.TrackListView.as_view(), name="track_list"),
    path("new/", views.TrackCreateView.as_view(), name="track_create"),
    path("<int:pk>/", views.TrackDetailView.as_view(), name="track_detail"),
    path("<int:pk>/edit/", views.TrackUpdateView.as_view(), name="track_update"),
    path("<int:pk>/delete/", views.TrackDeleteView.as_view(), name="track_delete"),
    path("<int:track_pk>/activities/new/", views.ActivityCreateView.as_view(), name="activity_create"),
    path("activities/<int:pk>/", views.ActivityDetailView.as_view(), name="activity_detail"),
    path("activities/<int:pk>/edit/", views.ActivityUpdateView.as_view(), name="activity_update"),
    path("activities/<int:pk>/delete/", views.ActivityDeleteView.as_view(), name="activity_delete"),
    path("activities/<int:activity_pk>/tests/new/", views.TestCaseCreateView.as_view(), name="test_case_create"),
    path("tests/<int:pk>/edit/", views.TestCaseUpdateView.as_view(), name="test_case_update"),
    path("tests/<int:pk>/delete/", views.TestCaseDeleteView.as_view(), name="test_case_delete"),
    path("submissions/<int:pk>/", views.SubmissionDetailView.as_view(), name="submission_detail"),
    path("browse/", student_views.CatalogView.as_view(), name="catalog"),
    path("browse/<int:pk>/", student_views.CatalogDetailView.as_view(), name="catalog_detail"),
    path("browse/<int:pk>/enroll/", student_views.EnrollView.as_view(), name="enroll"),
    path("browse/<int:pk>/drop/", student_views.DropView.as_view(), name="drop"),
    path("browse/activities/<int:pk>/", student_views.StudentActivityView.as_view(), name="student_activity"),
]
