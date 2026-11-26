from django import forms

from .models import PeerReview, Reflection

RATINGS = [(n, str(n)) for n in range(1, 6)]


class PeerReviewForm(forms.ModelForm):
    class Meta:
        model = PeerReview
        fields = ("correctness_rating", "readability_rating", "approach_rating", "comment")
        widgets = {
            "correctness_rating": forms.Select(choices=RATINGS),
            "readability_rating": forms.Select(choices=RATINGS),
            "approach_rating": forms.Select(choices=RATINGS),
            "comment": forms.Textarea(attrs={"rows": 4}),
        }
        help_texts = {"comment": "At least 20 characters."}


class ReflectionForm(forms.ModelForm):
    class Meta:
        model = Reflection
        fields = ("content",)
        labels = {"content": "What did you learn?"}
        widgets = {"content": forms.Textarea(attrs={"rows": 4})}
        help_texts = {"content": "At least 50 characters."}
