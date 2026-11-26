from django.urls import path

from . import views

urlpatterns = [
    path("submissions/<int:submission_pk>/review/", views.ReviewCreateView.as_view(), name="review_create"),
    path("<int:pk>/edit/", views.ReviewUpdateView.as_view(), name="review_update"),
    path("<int:pk>/delete/", views.ReviewDeleteView.as_view(), name="review_delete"),
]
