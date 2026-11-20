from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


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
