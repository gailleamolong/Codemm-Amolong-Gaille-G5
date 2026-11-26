from django.urls import path

from . import views

urlpatterns = [
    path("submissions/<int:submission_pk>/review/", views.ReviewCreateView.as_view(), name="review_create"),
    path("<int:pk>/edit/", views.ReviewUpdateView.as_view(), name="review_update"),
    path("<int:pk>/delete/", views.ReviewDeleteView.as_view(), name="review_delete"),
    path("submissions/<int:submission_pk>/reflection/", views.ReflectionCreateView.as_view(), name="reflection_create"),
    path("reflections/<int:pk>/edit/", views.ReflectionUpdateView.as_view(), name="reflection_update"),
    path("reflections/<int:pk>/delete/", views.ReflectionDeleteView.as_view(), name="reflection_delete"),
]
