from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, UpdateView

from accounts.models import User
from dashboard.views import RoleRequiredMixin
from tracks.models import Enrollment, Submission

from .forms import PeerReviewForm, ReflectionForm
from .models import PeerReview, Reflection


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
                return self.redirect_to_existing(existing)
        return super().dispatch(request, *args, **kwargs)

    def redirect_to_existing(self, review):
        messages.info(self.request, "You've already reviewed this submission. You can edit your review here.")
        return redirect("review_update", pk=review.pk)

    def form_valid(self, form):
        try:
            with transaction.atomic():
                return super().form_valid(form)
        except IntegrityError:
            existing = self.submission.reviews.filter(reviewer=self.request.user).first()
            if existing is None:
                raise
            return self.redirect_to_existing(existing)

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
        return PeerReview.objects.filter(
            reviewer=self.request.user,
            submission__activity__track__enrollments__student=self.request.user,
            submission__activity__track__enrollments__status=Enrollment.Status.ACTIVE,
        ).select_related("submission__activity")

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


class ReflectionCreateView(StudentMixin, SuccessMessageMixin, CreateView):
    """Only the student who made the submission writes its one reflection (BR-20)."""

    form_class = ReflectionForm
    template_name = "reviews/reflection_form.html"
    success_message = "Reflection saved."

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == User.Role.STUDENT:
            self.submission = get_object_or_404(
                Submission.objects.filter(enrollment__student=request.user), pk=kwargs["submission_pk"]
            )
            if hasattr(self.submission, "reflection"):
                return self.redirect_to_existing(self.submission.reflection)
        return super().dispatch(request, *args, **kwargs)

    def redirect_to_existing(self, reflection):
        messages.info(self.request, "You've already written a reflection. You can edit it here.")
        return redirect("reflection_update", pk=reflection.pk)

    def form_valid(self, form):
        try:
            with transaction.atomic():
                return super().form_valid(form)
        except IntegrityError:
            existing = Reflection.objects.filter(submission=self.submission).first()
            if existing is None:
                raise
            return self.redirect_to_existing(existing)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = Reflection(submission=self.submission)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["submission"] = self.submission
        return context

    def get_success_url(self):
        return reverse("submission_detail", args=[self.submission.pk])


class OwnReflectionMixin(StudentMixin):
    def get_queryset(self):
        return Reflection.objects.filter(submission__enrollment__student=self.request.user).select_related("submission")

    def get_success_url(self):
        return reverse("submission_detail", args=[self.object.submission_id])


class ReflectionUpdateView(OwnReflectionMixin, SuccessMessageMixin, UpdateView):
    form_class = ReflectionForm
    template_name = "reviews/reflection_form.html"
    success_message = "Reflection saved."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["submission"] = self.object.submission
        return context


class ReflectionDeleteView(OwnReflectionMixin, DeleteView):
    template_name = "reviews/confirm_delete_reflection.html"

    def form_valid(self, form):
        messages.success(self.request, "Reflection deleted.")
        return super().form_valid(form)
