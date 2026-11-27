from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Length
from django.db.models.lookups import GreaterThanOrEqual, LessThanOrEqual


class LearningTrack(models.Model):
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name="tracks")
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_published = models.BooleanField("published", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "learning_tracks"
        ordering = ["title"]
        constraints = [models.UniqueConstraint(fields=["instructor", "title"], name="unique_track_title_per_instructor")]

    def __str__(self):
        return self.title

    def clean(self):
        if self.instructor_id and self.instructor.role != "INSTRUCTOR":
            raise ValidationError({"instructor": "Only an instructor can own a learning track."})


class Activity(models.Model):
    class Difficulty(models.TextChoices):
        EASY = "EASY", "Easy"
        MEDIUM = "MEDIUM", "Medium"
        HARD = "HARD", "Hard"

    class Language(models.TextChoices):
        PYTHON = "PYTHON", "Python"
        JAVA = "JAVA", "Java"
        C = "C", "C"

    track = models.ForeignKey(LearningTrack, on_delete=models.CASCADE, related_name="activities")
    title = models.CharField(max_length=150)
    instructions = models.TextField()
    difficulty = models.CharField(max_length=6, choices=Difficulty.choices)
    language = models.CharField(max_length=10, choices=Language.choices)
    time_limit_ms = models.IntegerField(
        "time limit (ms)", default=2000, validators=[MinValueValidator(500), MaxValueValidator(10000)]
    )
    max_attempts = models.SmallIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(50)])
    due_at = models.DateTimeField("due date", null=True, blank=True)
    is_published = models.BooleanField("published", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "activities"
        ordering = ["created_at"]
        verbose_name_plural = "activities"
        constraints = [
            models.UniqueConstraint(fields=["track", "title"], name="unique_activity_title_per_track"),
            models.CheckConstraint(condition=Q(difficulty__in=["EASY", "MEDIUM", "HARD"]), name="activities_difficulty_check"),
            models.CheckConstraint(condition=Q(language__in=["PYTHON", "JAVA", "C"]), name="activities_language_check"),
            models.CheckConstraint(condition=Q(time_limit_ms__gte=500, time_limit_ms__lte=10000), name="activities_time_limit_check"),
            models.CheckConstraint(condition=Q(max_attempts__gte=1, max_attempts__lte=50), name="activities_max_attempts_check"),
        ]

    def __str__(self):
        return self.title


class Enrollment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        DROPPED = "DROPPED", "Dropped"

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name="enrollments")
    track = models.ForeignKey(LearningTrack, on_delete=models.CASCADE, related_name="enrollments")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "enrollments"
        ordering = ["-enrolled_at"]
        constraints = [
            models.UniqueConstraint(fields=["student", "track"], name="unique_enrollment_per_student_track"),
            models.CheckConstraint(condition=Q(status__in=["ACTIVE", "DROPPED"]), name="enrollments_status_check"),
        ]

    def __str__(self):
        return f"{self.student} in {self.track}"


class TestCase(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="test_cases")
    seq_no = models.SmallIntegerField("number", validators=[MinValueValidator(1)])
    input_data = models.TextField("input", blank=True, default="")
    expected_output = models.TextField()
    is_sample = models.BooleanField("visible sample", default=False)
    points = models.SmallIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        db_table = "test_cases"
        ordering = ["seq_no"]
        constraints = [
            models.UniqueConstraint(fields=["activity", "seq_no"], name="unique_test_case_number_per_activity"),
            models.CheckConstraint(condition=Q(seq_no__gte=1), name="test_cases_seq_no_check"),
            models.CheckConstraint(condition=Q(points__gte=1), name="test_cases_points_check"),
        ]

    def __str__(self):
        return f"Test {self.seq_no}"


class Submission(models.Model):
    class Verdict(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        WRONG_ANSWER = "WRONG_ANSWER", "Wrong answer"
        RUNTIME_ERROR = "RUNTIME_ERROR", "Runtime error"
        TIME_LIMIT_EXCEEDED = "TIME_LIMIT_EXCEEDED", "Time limit exceeded"
        COMPILATION_ERROR = "COMPILATION_ERROR", "Compilation error"

    MAX_CODE_LENGTH = 65535

    enrollment = models.ForeignKey(Enrollment, on_delete=models.RESTRICT, related_name="submissions")
    activity = models.ForeignKey(Activity, on_delete=models.RESTRICT, related_name="submissions")
    attempt_no = models.SmallIntegerField(validators=[MinValueValidator(1)])
    source_code = models.TextField()
    verdict = models.CharField(max_length=20, choices=Verdict.choices, default=Verdict.PENDING)
    passed_count = models.SmallIntegerField(default=0, validators=[MinValueValidator(0)])
    total_count = models.SmallIntegerField(default=0, validators=[MinValueValidator(0)])
    score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "submissions"
        ordering = ["-submitted_at"]
        constraints = [
            models.UniqueConstraint(fields=["enrollment", "activity", "attempt_no"], name="unique_attempt_per_student_activity"),
            models.CheckConstraint(condition=Q(attempt_no__gte=1), name="submissions_attempt_no_check"),
            models.CheckConstraint(
                condition=Q(GreaterThanOrEqual(Length("source_code"), 1), LessThanOrEqual(Length("source_code"), 65535)),
                name="submissions_source_code_length_check",
            ),
            models.CheckConstraint(condition=Q(verdict__in=["PENDING", "ACCEPTED", "WRONG_ANSWER", "RUNTIME_ERROR", "TIME_LIMIT_EXCEEDED", "COMPILATION_ERROR"]), name="submissions_verdict_check"),
            models.CheckConstraint(condition=Q(passed_count__gte=0, total_count__gte=0), name="submissions_counts_check"),
            models.CheckConstraint(condition=Q(passed_count__lte=F("total_count")), name="submissions_passed_lte_total_check"),
            models.CheckConstraint(
                condition=~Q(verdict="ACCEPTED") | Q(total_count__gt=0, passed_count=F("total_count")),
                name="submissions_accepted_all_passed_check",
            ),
            models.CheckConstraint(condition=Q(score__gte=0, score__lte=100) | Q(score__isnull=True), name="submissions_score_check"),
            models.CheckConstraint(
                condition=Q(verdict="PENDING", score__isnull=True) | (~Q(verdict="PENDING") & Q(score__isnull=False)),
                name="submissions_pending_has_no_score_check",
            ),
        ]

    def __str__(self):
        return f"Attempt {self.attempt_no} on {self.activity}"


class TestResult(models.Model):
    class Status(models.TextChoices):
        PASSED = "PASSED", "Passed"
        FAILED = "FAILED", "Failed"
        RUNTIME_ERROR = "RUNTIME_ERROR", "Runtime error"
        TIME_LIMIT_EXCEEDED = "TIME_LIMIT_EXCEEDED", "Time limit exceeded"
        COMPILATION_ERROR = "COMPILATION_ERROR", "Compilation error"

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="results")
    test_case = models.ForeignKey(TestCase, on_delete=models.RESTRICT, related_name="results")
    status = models.CharField(max_length=20, choices=Status.choices)
    actual_output = models.TextField(null=True, blank=True)
    exec_time_ms = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])

    class Meta:
        db_table = "test_results"
        ordering = ["test_case__seq_no"]
        constraints = [
            models.UniqueConstraint(fields=["submission", "test_case"], name="unique_result_per_test_case"),
            models.CheckConstraint(condition=Q(status__in=["PASSED", "FAILED", "RUNTIME_ERROR", "TIME_LIMIT_EXCEEDED", "COMPILATION_ERROR"]), name="test_results_status_check"),
            models.CheckConstraint(condition=Q(exec_time_ms__gte=0) | Q(exec_time_ms__isnull=True), name="test_results_exec_time_check"),
        ]
