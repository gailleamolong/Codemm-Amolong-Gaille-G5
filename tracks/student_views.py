from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, ListView

from accounts.models import User
from codemm import ratelimit
from dashboard.views import RoleRequiredMixin

from . import judge0
from .forms import SearchForm, SubmissionForm, filter_activities, filter_tracks
from reviews.views import reviewable_submissions

from .grading import SubmissionBlocked, check, save_submission, submission_blocked
from .models import Activity, Enrollment, LearningTrack, Submission


CODE_CHECKS_PER_MINUTE = 10


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
        with transaction.atomic():
            enrollment, created = Enrollment.objects.select_for_update().get_or_create(student=request.user, track=track)
            already_active = not created and enrollment.status == Enrollment.Status.ACTIVE
            if not already_active:
                enrollment.status = Enrollment.Status.ACTIVE
                enrollment.save()
        if already_active:
            messages.error(request, f"You're already enrolled in {track.title}.")
        else:
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
        my_reviews = {r.submission_id: r.pk for r in self.request.user.reviews_written.filter(submission__activity=activity)}
        to_review = [(s, my_reviews.get(s.pk)) for s in reviewable_submissions(self.request.user).filter(activity=activity)]
        return super().get_context_data(
            to_review=to_review,
            samples=activity.test_cases.filter(is_sample=True),
            attempts=attempts,
            attempts_left=max(activity.max_attempts - attempts.count(), 0),
            blocked=submission_blocked(activity, attempts.count()),
            **kwargs,
        )

    def post(self, request, *args, **kwargs):
        self.object = activity = self.get_object()
        enrollment = get_object_or_404(Enrollment, student=request.user, track=activity.track, status=Enrollment.Status.ACTIVE)
        form = SubmissionForm(request.POST)
        if ratelimit.record(f"judge0:{request.user.pk}", 60) > CODE_CHECKS_PER_MINUTE:
            messages.error(request, "You're running code too often. Wait a minute and try again.")
            return self.render_to_response(self.get_context_data(form=form))
        if request.POST.get("action") == "run":
            return self.run_code(form)
        blocked = submission_blocked(activity, enrollment.submissions.filter(activity=activity).count())
        if blocked:
            messages.error(request, blocked)
        elif form.is_valid():
            code = form.cleaned_data["source_code"]
            try:
                results = check(activity, code)
                submission = save_submission(enrollment, activity, code, results)
            except (judge0.Judge0Error, SubmissionBlocked) as error:
                messages.error(request, str(error))
            else:
                messages.success(request, f"Attempt {submission.attempt_no}: {submission.get_verdict_display()}.")
                return redirect("submission_detail", pk=submission.pk)
        return self.render_to_response(self.get_context_data(form=form))

    def run_code(self, form):
        """Run once with the student's own input. Nothing is saved and no attempt is used."""
        run_result = None
        if form.is_valid():
            data = form.cleaned_data
            try:
                run_result = judge0.run(self.object.language, data["source_code"], data["stdin"], self.object.time_limit_ms)
            except judge0.Judge0Error as error:
                messages.error(self.request, str(error))
        return self.render_to_response(self.get_context_data(form=form, run_result=run_result, run_status=run_label(run_result)))


def run_label(result):
    if result is None:
        return ""
    if result["status"] == judge0.COMPILE_ERROR:
        return "Compilation error"
    if result["status"] == judge0.TIME_LIMIT:
        return "Time limit exceeded"
    if result["status"] in judge0.RUNTIME_ERRORS:
        return "Runtime error"
    return "Finished"
