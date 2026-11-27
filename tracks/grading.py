from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Max
from django.utils import timezone

from . import judge0
from .models import Enrollment, Submission, TestResult

Status = TestResult.Status
Verdict = Submission.Verdict


class SubmissionBlocked(Exception):
    pass


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


def same_output(actual, expected):
    """Ignore trailing spaces on each line and trailing blank lines."""
    def clean(text):
        return "\n".join(line.rstrip() for line in text.rstrip().splitlines())
    return clean(actual) == clean(expected)


def check(activity, source_code):
    """Run the code against every test case. Raises judge0.Judge0Error if the checker fails."""
    results = []
    for test in activity.test_cases.all():
        outcome = judge0.run(activity.language, source_code, test.input_data, activity.time_limit_ms)
        if outcome["status"] == judge0.COMPILE_ERROR:
            return [(t, Status.COMPILATION_ERROR, outcome["error"], None) for t in activity.test_cases.all()]
        if outcome["status"] == judge0.TIME_LIMIT:
            status = Status.TIME_LIMIT_EXCEEDED
        elif outcome["status"] in judge0.RUNTIME_ERRORS:
            status = Status.RUNTIME_ERROR
        else:
            status = Status.PASSED if same_output(outcome["stdout"], test.expected_output) else Status.FAILED
        results.append((test, status, outcome["stdout"] or outcome["error"], outcome["time_ms"]))
    return results


def verdict_for(statuses):
    if Status.COMPILATION_ERROR in statuses:
        return Verdict.COMPILATION_ERROR
    if all(s == Status.PASSED for s in statuses):
        return Verdict.ACCEPTED
    if Status.RUNTIME_ERROR in statuses:
        return Verdict.RUNTIME_ERROR
    if Status.TIME_LIMIT_EXCEEDED in statuses:
        return Verdict.TIME_LIMIT_EXCEEDED
    return Verdict.WRONG_ANSWER


def save_submission(enrollment, activity, source_code, results):
    """Store the attempt and its test results together, numbering attempts without gaps or duplicates."""
    total_points = sum(test.points for test, *_ in results)
    passed_points = sum(test.points for test, status, *_ in results if status == Status.PASSED)
    with transaction.atomic():
        Enrollment.objects.select_for_update().get(pk=enrollment.pk)
        activity.refresh_from_db(fields=["max_attempts", "due_at"])
        attempts = Submission.objects.filter(enrollment=enrollment, activity=activity).aggregate(
            used=Count("pk"), last=Max("attempt_no"),
        )
        blocked = submission_blocked(activity, attempts["used"])
        if blocked:
            raise SubmissionBlocked(blocked)
        submission = Submission.objects.create(
            enrollment=enrollment,
            activity=activity,
            attempt_no=(attempts["last"] or 0) + 1,
            source_code=source_code,
            verdict=verdict_for([status for _, status, *_ in results]),
            passed_count=sum(1 for _, status, *_ in results if status == Status.PASSED),
            total_count=len(results),
            score=(Decimal(100) * passed_points / total_points).quantize(Decimal("0.01")),
        )
        TestResult.objects.bulk_create(
            TestResult(submission=submission, test_case=test, status=status, actual_output=output, exec_time_ms=time_ms)
            for test, status, output, time_ms in results
        )
    return submission
