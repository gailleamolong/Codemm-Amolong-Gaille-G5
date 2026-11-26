from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, UpdateView

from accounts.models import User
from dashboard.views import RoleRequiredMixin
from tracks.models import Enrollment, Submission

from .forms import PeerReviewForm
from .models import PeerReview


class StudentMixin(RoleRequiredMixin):
    role = User.Role.STUDENT


def reviewable_submissions(student):
    """Accepted submissions by classmates in tracks where this student is actively enrolled (BR-17)."""
    return (
        Submission.objects.filter(
            verdict=Submission.Verdict.ACCEPTED,
            activity__track__enrollments__student=student,
            activity__track__enrollments__status=Enrollment.Status.ACTIVE,
        )
        .exclude(enrollment__student=student)
        .select_related("activity", "enrollment__student")
    )


class ReviewCreateView(StudentMixin, SuccessMessageMixin, CreateView):
    form_class = PeerReviewForm
    template_name = "reviews/review_form.html"
    success_message = "Review posted."

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == User.Role.STUDENT:
            self.submission = get_object_or_404(reviewable_submissions(request.user), pk=kwargs["submission_pk"])
            existing = self.submission.reviews.filter(reviewer=request.user).first()
            if existing:
                messages.info(request, "You've already reviewed this submission. You can edit your review here.")
                return redirect("review_update", pk=existing.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = PeerReview(submission=self.submission, reviewer=self.request.user)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["submission"] = self.submission
        return context

    def get_success_url(self):
        return reverse("student_activity", args=[self.submission.activity_id])


class OwnReviewMixin(StudentMixin):
    def get_queryset(self):
        return PeerReview.objects.filter(reviewer=self.request.user).select_related("submission__activity")

    def get_success_url(self):
        return reverse("student_activity", args=[self.object.submission.activity_id])


class ReviewUpdateView(OwnReviewMixin, SuccessMessageMixin, UpdateView):
    form_class = PeerReviewForm
    template_name = "reviews/review_form.html"
    success_message = "Review saved."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["submission"] = self.object.submission
        return context


class ReviewDeleteView(OwnReviewMixin, DeleteView):
    template_name = "reviews/confirm_delete.html"

    def form_valid(self, form):
        messages.success(self.request, "Review deleted.")
        return super().form_valid(form)
