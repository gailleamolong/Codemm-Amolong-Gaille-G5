from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from accounts.models import User
from dashboard.views import RoleRequiredMixin

from .forms import ActivityForm, TrackForm
from .models import Activity, LearningTrack


class InstructorMixin(RoleRequiredMixin):
    role = User.Role.INSTRUCTOR


class OwnTrackMixin(InstructorMixin):
    """Instructors only ever see and change their own tracks."""

    def get_queryset(self):
        return LearningTrack.objects.filter(instructor=self.request.user)


class TrackListView(OwnTrackMixin, ListView):
    template_name = "tracks/track_list.html"
    context_object_name = "tracks"

    def get_queryset(self):
        return super().get_queryset().prefetch_related("activities")


class TrackDetailView(OwnTrackMixin, DetailView):
    template_name = "tracks/track_detail.html"
    context_object_name = "track"


class TrackCreateView(InstructorMixin, SuccessMessageMixin, CreateView):
    form_class = TrackForm
    template_name = "tracks/track_form.html"
    success_message = "Track created."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = LearningTrack(instructor=self.request.user)
        return kwargs

    def get_success_url(self):
        return reverse("track_detail", args=[self.object.pk])


class TrackUpdateView(OwnTrackMixin, SuccessMessageMixin, UpdateView):
    form_class = TrackForm
    template_name = "tracks/track_form.html"
    success_message = "Track saved."

    def get_success_url(self):
        return reverse("track_detail", args=[self.object.pk])


class TrackDeleteView(OwnTrackMixin, DeleteView):
    template_name = "tracks/confirm_delete.html"
    success_url = reverse_lazy("track_list")

    def form_valid(self, form):
        messages.success(self.request, f"Deleted {self.object.title}.")
        return super().form_valid(form)


class OwnActivityMixin(InstructorMixin):
    def get_queryset(self):
        return Activity.objects.filter(track__instructor=self.request.user)

    def get_success_url(self):
        return reverse("track_detail", args=[self.object.track_id])


class ActivityCreateView(InstructorMixin, SuccessMessageMixin, CreateView):
    form_class = ActivityForm
    template_name = "tracks/activity_form.html"
    success_message = "Activity added."

    def get_form_kwargs(self):
        self.track = get_object_or_404(LearningTrack, pk=self.kwargs["track_pk"], instructor=self.request.user)
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = Activity(track=self.track)
        return kwargs

    def get_context_data(self, **kwargs):
        return super().get_context_data(track=self.track, **kwargs)

    def get_success_url(self):
        return reverse("track_detail", args=[self.track.pk])


class ActivityDetailView(OwnActivityMixin, DetailView):
    template_name = "tracks/activity_detail.html"
    context_object_name = "activity"


class ActivityUpdateView(OwnActivityMixin, SuccessMessageMixin, UpdateView):
    form_class = ActivityForm
    template_name = "tracks/activity_form.html"
    success_message = "Activity saved."

    def get_context_data(self, **kwargs):
        return super().get_context_data(track=self.object.track, **kwargs)


class ActivityDeleteView(OwnActivityMixin, DeleteView):
    template_name = "tracks/confirm_delete.html"

    def form_valid(self, form):
        messages.success(self.request, f"Deleted {self.object.title}.")
        return super().form_valid(form)
