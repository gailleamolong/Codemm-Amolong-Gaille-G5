from django.conf import settings
from django.core.validators import MaxValueValidator, MinLengthValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Length
from django.db.models.lookups import GreaterThanOrEqual

from tracks.models import Submission

RATING = [MinValueValidator(1), MaxValueValidator(5)]


class PeerReview(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name="reviews_written")
    correctness_rating = models.SmallIntegerField("correctness", validators=RATING)
    readability_rating = models.SmallIntegerField("readability", validators=RATING)
    approach_rating = models.SmallIntegerField("approach", validators=RATING)
    comment = models.TextField(validators=[MinLengthValidator(20)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "peer_reviews"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["submission", "reviewer"], name="unique_review_per_reviewer"),
            models.CheckConstraint(
                condition=Q(correctness_rating__range=(1, 5), readability_rating__range=(1, 5), approach_rating__range=(1, 5)),
                name="peer_reviews_ratings_check",
            ),
            models.CheckConstraint(condition=Q(GreaterThanOrEqual(Length("comment"), 20)), name="peer_reviews_comment_length_check"),
        ]

    def __str__(self):
        return f"Review of {self.submission}"
