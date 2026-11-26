import csv

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from django.views.generic import TemplateView

from accounts.models import User
from dashboard.views import RoleRequiredMixin
from tracks.models import Enrollment, LearningTrack

from .services import pass_rate_rows, progress_rows


def spreadsheet_safe(value):
    """Stop spreadsheet apps from running a cell that starts with a formula character."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def csv_response(filename, header, rows):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(header)
    for row in rows:
        writer.writerow([spreadsheet_safe(cell) for cell in row])
    return response


class InstructorTrackMixin(RoleRequiredMixin):
    role = User.Role.INSTRUCTOR

    def get_track(self):
        return get_object_or_404(LearningTrack, pk=self.kwargs["pk"], instructor=self.request.user)


class ProgressReportView(InstructorTrackMixin, TemplateView):
    template_name = "reports/progress.html"

    def get(self, request, *args, **kwargs):
        track = self.get_track()
        activities, rows = progress_rows(track)
        if request.GET.get("format") == "csv":
            return csv_response(
                f"{slugify(track.title)}-progress.csv",
                ["Student", "Status", "Attempted", "Accepted", "Reviews received"] + [f"Best: {a.title}" for a in activities],
                ([r["student"].get_full_name() or r["student"].username, r["status"], r["attempted"], r["accepted"],
                  r["reviews_received"]] + r["best_scores"] for r in rows),
            )
        return self.render_to_response(self.get_context_data(track=track, activities=activities, rows=rows))


class PassRateReportView(InstructorTrackMixin, TemplateView):
    template_name = "reports/pass_rate.html"

    def get(self, request, *args, **kwargs):
        track = self.get_track()
        rows = pass_rate_rows(track)
        if request.GET.get("format") == "csv":
            return csv_response(
                f"{slugify(track.title)}-pass-rate.csv",
                ["Activity", "Students attempted", "Students accepted", "Pass rate (%)", "Average attempts", "Most-failed test"],
                ([r["activity"].title, r["attempted"], r["accepted"], r["pass_rate"], r["average_attempts"], r["most_failed"]]
                 for r in rows),
            )
        return self.render_to_response(self.get_context_data(track=track, rows=rows))


class MyProgressView(RoleRequiredMixin, TemplateView):
    role = User.Role.STUDENT
    template_name = "reports/my_progress.html"

    def get_context_data(self, **kwargs):
        reports = []
        for enrollment in self.request.user.enrollments.select_related("track").filter(status=Enrollment.Status.ACTIVE):
            activities, rows = progress_rows(enrollment.track, students=[self.request.user])
            row = rows[0]
            reports.append({"track": enrollment.track, "total": len(activities), "row": row,
                            "scores": list(zip(activities, row["best_scores"]))})
        return super().get_context_data(reports=reports, **kwargs)
