from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from accounts.models import User
from dashboard.views import RoleRequiredMixin

from .forms import ActivityForm, SearchForm, TestCaseForm, TrackForm, filter_activities, filter_tracks
from .models import Activity, LearningTrack, Submission, TestCase


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
        self.search = SearchForm(self.request.GET)
        return filter_tracks(super().get_queryset(), self.search).prefetch_related("activities")

    def get_context_data(self, **kwargs):
        return super().get_context_data(search=self.search, **kwargs)


class TrackDetailView(OwnTrackMixin, DetailView):
    template_name = "tracks/track_detail.html"
    context_object_name = "track"

    def get_context_data(self, **kwargs):
        search = SearchForm(self.request.GET)
        activities = filter_activities(self.object.activities.all(), search)
        return super().get_context_data(search=search, activities=activities, **kwargs)


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
        if Submission.objects.filter(activity__track=self.object).exists():
            messages.error(self.request, "This track has submissions, so it can't be deleted. Unpublish it instead.")
            return redirect("track_detail", pk=self.object.pk)
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
        context = super().get_context_data(**kwargs)
        context["track"] = self.track
        return context

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
        if self.object.submissions.exists():
            messages.error(self.request, "This activity has submissions, so it can't be deleted. Unpublish it instead.")
            return redirect("activity_detail", pk=self.object.pk)
        messages.success(self.request, f"Deleted {self.object.title}.")
        return super().form_valid(form)


class OwnTestCaseMixin(InstructorMixin):
    def get_queryset(self):
        return TestCase.objects.filter(activity__track__instructor=self.request.user)

    def get_success_url(self):
        return reverse("activity_detail", args=[self.object.activity_id])


class TestCaseCreateView(InstructorMixin, SuccessMessageMixin, CreateView):
    form_class = TestCaseForm
    template_name = "tracks/test_case_form.html"
    success_message = "Test case added."

    def get_form_kwargs(self):
        self.activity = get_object_or_404(
            Activity, pk=self.kwargs["activity_pk"], track__instructor=self.request.user
        )
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = TestCase(activity=self.activity)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["activity"] = self.activity
        return context

    def get_success_url(self):
        return reverse("activity_detail", args=[self.activity.pk])


class TestCaseUpdateView(OwnTestCaseMixin, SuccessMessageMixin, UpdateView):
    form_class = TestCaseForm
    template_name = "tracks/test_case_form.html"
    success_message = "Test case saved."

    def get_context_data(self, **kwargs):
        return super().get_context_data(activity=self.object.activity, **kwargs)


class TestCaseDeleteView(OwnTestCaseMixin, DeleteView):
    template_name = "tracks/confirm_delete.html"

    def form_valid(self, form):
        activity = self.object.activity
        if self.object.results.exists():
            messages.error(self.request, "This test case already has results, so it can't be deleted.")
            return redirect("activity_detail", pk=activity.pk)
        if activity.is_published and activity.test_cases.count() == 1:
            messages.error(self.request, "Unpublish the activity or add another test case first.")
            return redirect("activity_detail", pk=activity.pk)
        messages.success(self.request, "Test case deleted.")
        return super().form_valid(form)


class SubmissionDetailView(LoginRequiredMixin, DetailView):
    """Students see their own attempts; instructors see attempts on their own activities."""

    template_name = "tracks/submission_detail.html"
    context_object_name = "submission"

    def get_queryset(self):
        submissions = Submission.objects.select_related("activity__track", "enrollment__student")
        user = self.request.user
        if user.role == User.Role.STUDENT:
            return submissions.filter(enrollment__student=user)
        if user.role == User.Role.INSTRUCTOR:
            return submissions.filter(activity__track__instructor=user)
        return submissions.none()

    def get_context_data(self, **kwargs):
        results = self.object.results.select_related("test_case")
        return super().get_context_data(results=results, **kwargs)
