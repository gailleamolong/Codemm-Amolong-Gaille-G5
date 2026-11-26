from django.db.models import Count, Max, Q

from reviews.models import PeerReview
from tracks.models import Submission, TestResult


def progress_rows(track, students=None):
    """One row per enrolled student: activities attempted and accepted, best score per activity, reviews received."""
    activities = list(track.activities.order_by("created_at"))
    enrollments = track.enrollments.select_related("student").order_by("student__last_name", "student__first_name")
    if students is not None:
        enrollments = enrollments.filter(student__in=students)
    best = {
        (row["enrollment"], row["activity"]): row
        for row in Submission.objects.filter(activity__track=track)
        .values("enrollment", "activity")
        .annotate(best=Max("score"), accepted=Count("id", filter=Q(verdict=Submission.Verdict.ACCEPTED)))
    }
    reviews = dict(
        PeerReview.objects.filter(submission__activity__track=track)
        .values_list("submission__enrollment").annotate(n=Count("id"))
    )
    rows = []
    for enrollment in enrollments:
        scores = [best.get((enrollment.pk, a.pk)) for a in activities]
        rows.append({
            "student": enrollment.student,
            "status": enrollment.get_status_display(),
            "attempted": sum(1 for s in scores if s),
            "accepted": sum(1 for s in scores if s and s["accepted"]),
            "best_scores": [s["best"] if s else None for s in scores],
            "reviews_received": reviews.get(enrollment.pk, 0),
        })
    return activities, rows


def pass_rate_rows(track):
    """One row per activity: students attempted and accepted, pass rate, average attempts, most-failed test case."""
    rows = []
    for activity in track.activities.order_by("created_at"):
        submissions = Submission.objects.filter(activity=activity)
        attempted = submissions.values("enrollment").distinct().count()
        accepted = submissions.filter(verdict=Submission.Verdict.ACCEPTED).values("enrollment").distinct().count()
        most_failed = (
            TestResult.objects.filter(submission__activity=activity).exclude(status=TestResult.Status.PASSED)
            .values("test_case__seq_no").annotate(n=Count("id")).order_by("-n", "test_case__seq_no").first()
        )
        rows.append({
            "activity": activity,
            "attempted": attempted,
            "accepted": accepted,
            "pass_rate": round(100 * accepted / attempted) if attempted else None,
            "average_attempts": round(submissions.count() / attempted, 1) if attempted else None,
            "most_failed": most_failed["test_case__seq_no"] if most_failed else None,
        })
    return rows
