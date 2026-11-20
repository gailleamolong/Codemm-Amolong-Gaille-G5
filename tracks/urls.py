from django.urls import path

from . import views

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
]
