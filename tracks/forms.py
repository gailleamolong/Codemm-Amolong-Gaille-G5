from django import forms

from .models import Activity, LearningTrack, TestCase


class TrackForm(forms.ModelForm):
    class Meta:
        model = LearningTrack
        fields = ("title", "description", "is_published")

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        taken = LearningTrack.objects.filter(instructor=self.instance.instructor, title__iexact=title)
        if taken.exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("You already have a track with this title.")
        return title


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ("title", "instructions", "difficulty", "language", "time_limit_ms", "max_attempts", "due_at", "is_published")
        widgets = {"due_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")}

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        taken = Activity.objects.filter(track=self.instance.track, title__iexact=title)
        if taken.exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This track already has an activity with this title.")
        return title

    def clean(self):
        cleaned = super().clean()
        has_tests = self.instance.pk and self.instance.test_cases.exists()
        if cleaned.get("is_published") and not has_tests:
            self.add_error("is_published", "Add at least one test case before publishing.")
        return cleaned


class TestCaseForm(forms.ModelForm):
    class Meta:
        model = TestCase
        fields = ("seq_no", "input_data", "expected_output", "is_sample", "points")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            last = self.instance.activity.test_cases.order_by("-seq_no").first()
            self.initial["seq_no"] = last.seq_no + 1 if last else 1

    def clean_seq_no(self):
        seq_no = self.cleaned_data["seq_no"]
        taken = TestCase.objects.filter(activity=self.instance.activity, seq_no=seq_no)
        if taken.exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This activity already has a test case with this number.")
        return seq_no
