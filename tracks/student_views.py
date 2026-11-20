from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, ListView

from accounts.models import User
from dashboard.views import RoleRequiredMixin

from .models import Activity, Enrollment, LearningTrack


class StudentMixin(RoleRequiredMixin):
    role = User.Role.STUDENT


class CatalogView(StudentMixin, ListView):
    template_name = "tracks/catalog.html"
    context_object_name = "tracks"

    def get_queryset(self):
        return LearningTrack.objects.filter(is_published=True).select_related("instructor")

    def get_context_data(self, **kwargs):
        active = self.request.user.enrollments.filter(status=Enrollment.Status.ACTIVE)
        return super().get_context_data(enrolled_ids=set(active.values_list("track_id", flat=True)), **kwargs)


class CatalogDetailView(StudentMixin, DetailView):
    template_name = "tracks/catalog_detail.html"
    context_object_name = "track"

    def get_queryset(self):
        return LearningTrack.objects.filter(is_published=True)

    def get_context_data(self, **kwargs):
        enrolled = self.object.enrollments.filter(student=self.request.user, status=Enrollment.Status.ACTIVE).exists()
        activities = self.object.activities.filter(is_published=True) if enrolled else []
        return super().get_context_data(enrolled=enrolled, activities=activities, **kwargs)


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
