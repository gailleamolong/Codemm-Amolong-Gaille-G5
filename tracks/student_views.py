from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView

from accounts.models import User
from dashboard.views import RoleRequiredMixin

from . import judge0
from .forms import SearchForm, SubmissionForm, filter_activities, filter_tracks
from .grading import check, save_submission
from .models import Activity, Enrollment, LearningTrack, Submission


class StudentMixin(RoleRequiredMixin):
    role = User.Role.STUDENT


class CatalogView(StudentMixin, ListView):
    template_name = "tracks/catalog.html"
    context_object_name = "tracks"

    def get_queryset(self):
        self.search = SearchForm(self.request.GET)
        tracks = LearningTrack.objects.filter(is_published=True).select_related("instructor")
        return filter_tracks(tracks, self.search)

    def get_context_data(self, **kwargs):
        active = self.request.user.enrollments.filter(status=Enrollment.Status.ACTIVE)
        enrolled_ids = set(active.values_list("track_id", flat=True))
        return super().get_context_data(enrolled_ids=enrolled_ids, search=self.search, **kwargs)


class CatalogDetailView(StudentMixin, DetailView):
    template_name = "tracks/catalog_detail.html"
    context_object_name = "track"

    def get_queryset(self):
        return LearningTrack.objects.filter(is_published=True)

    def get_context_data(self, **kwargs):
        enrolled = self.object.enrollments.filter(student=self.request.user, status=Enrollment.Status.ACTIVE).exists()
        search = SearchForm(self.request.GET)
        activities = filter_activities(self.object.activities.filter(is_published=True), search) if enrolled else []
        return super().get_context_data(enrolled=enrolled, activities=activities, search=search, **kwargs)


class EnrollView(StudentMixin, View):
    def post(self, request, pk):
        track = get_object_or_404(LearningTrack, pk=pk, is_published=True)
        enrollment, created = Enrollment.objects.get_or_create(student=request.user, track=track)
        if not created and enrollment.status == Enrollment.Status.ACTIVE:
            messages.error(request, f"You're already enrolled in {track.title}.")
        else:
            enrollment.status = Enrollment.Status.ACTIVE
            enrollment.save()
            messages.success(request, f"Enrolled in {track.title}.")
        return redirect("catalog_detail", pk=track.pk)


class DropView(StudentMixin, View):
    def post(self, request, pk):
        enrollment = get_object_or_404(Enrollment, track_id=pk, student=request.user, status=Enrollment.Status.ACTIVE)
        enrollment.status = Enrollment.Status.DROPPED
        enrollment.save()
        messages.success(request, f"Dropped {enrollment.track.title}.")
        return redirect("student_dashboard")


class StudentActivityView(StudentMixin, DetailView):
    template_name = "tracks/student_activity.html"
    context_object_name = "activity"

    def get_queryset(self):
        return Activity.objects.filter(
            is_published=True,
            track__is_published=True,
            track__enrollments__student=self.request.user,
            track__enrollments__status=Enrollment.Status.ACTIVE,
        )

    def get_context_data(self, **kwargs):
        activity = self.object
        attempts = Submission.objects.filter(activity=activity, enrollment__student=self.request.user)
        kwargs.setdefault("form", SubmissionForm())
        return super().get_context_data(
            samples=activity.test_cases.filter(is_sample=True),
            attempts=attempts,
            attempts_left=max(activity.max_attempts - attempts.count(), 0),
            blocked=submission_blocked(activity, attempts.count()),
            **kwargs,
        )

    def post(self, request, *args, **kwargs):
        self.object = activity = self.get_object()
        enrollment = Enrollment.objects.get(student=request.user, track=activity.track)
        form = SubmissionForm(request.POST)
        blocked = submission_blocked(activity, enrollment.submissions.filter(activity=activity).count())
        if blocked:
            messages.error(request, blocked)
        elif form.is_valid():
            code = form.cleaned_data["source_code"]
            try:
                results = check(activity, code)
            except judge0.Judge0Error as error:
                messages.error(request, str(error))
            else:
                submission = save_submission(enrollment, activity, code, results)
                messages.success(request, f"Attempt {submission.attempt_no}: {submission.get_verdict_display()}.")
                return redirect("submission_detail", pk=submission.pk)
        return self.render_to_response(self.get_context_data(form=form))


def submission_blocked(activity, attempts_used):
    """The reason a student can't submit right now, or None (BR-11, BR-23)."""
    if not judge0.is_configured():
        return "Code checking isn't set up yet, so submissions are closed."
    if activity.due_at and timezone.now() > activity.due_at:
        return "The due date has passed."
    if attempts_used >= activity.max_attempts:
        return "You've used all your attempts for this activity."
    if not activity.test_cases.exists():
        return "This activity has no test cases yet."
    return None
