from django import forms
from django.db.models import Q
from django.utils import timezone

from .models import Activity, LearningTrack, Submission, TestCase


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

    def clean_due_at(self):
        due_at = self.cleaned_data.get("due_at")
        unchanged = self.instance.pk and due_at == self.instance.due_at
        if due_at and not unchanged and due_at <= timezone.now():
            raise forms.ValidationError("Pick a due date in the future.")
        return due_at

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


class SearchForm(forms.Form):
    """Optional GET filters. Unknown choices are rejected instead of ignored silently."""

    q = forms.CharField(label="Search", required=False, max_length=100)
    difficulty = forms.ChoiceField(choices=[("", "Any difficulty"), *Activity.Difficulty.choices], required=False)
    language = forms.ChoiceField(choices=[("", "Any language"), *Activity.Language.choices], required=False)
    status = forms.ChoiceField(choices=[("", "Any status"), ("published", "Published"), ("draft", "Draft")], required=False)
    verdict = forms.ChoiceField(choices=[("", "Any verdict"), *Submission.Verdict.choices], required=False)

    def value(self, name):
        return self.cleaned_data.get(name) if self.is_valid() else ""


def filter_tracks(tracks, form):
    q = form.value("q").strip()
    if q:
        tracks = tracks.filter(
            Q(title__icontains=q) | Q(description__icontains=q)
            | Q(instructor__first_name__icontains=q) | Q(instructor__last_name__icontains=q)
        )
    if form.value("language"):
        tracks = tracks.filter(activities__language=form.value("language"), activities__is_published=True).distinct()
    if form.value("status"):
        tracks = tracks.filter(is_published=form.value("status") == "published")
    return tracks


def filter_activities(activities, form):
    q = form.value("q").strip()
    if q:
        activities = activities.filter(Q(title__icontains=q) | Q(instructions__icontains=q))
    if form.value("difficulty"):
        activities = activities.filter(difficulty=form.value("difficulty"))
    if form.value("language"):
        activities = activities.filter(language=form.value("language"))
    return activities


class SubmissionForm(forms.Form):
    source_code = forms.CharField(
        label="Your code", strip=False, max_length=Submission.MAX_CODE_LENGTH,
        widget=forms.Textarea(attrs={"rows": 14, "spellcheck": "false", "class": "code"}),
    )
    stdin = forms.CharField(
        label="Input for Run", required=False, strip=False, max_length=10000,
        widget=forms.Textarea(attrs={"rows": 3, "spellcheck": "false", "class": "code small"}),
    )

    def clean_source_code(self):
        code = self.cleaned_data["source_code"]
        if not code.strip():
            raise forms.ValidationError("Write some code before submitting.")
        return code


def filter_submissions(submissions, form):
    q = form.value("q").strip()
    if q:
        submissions = submissions.filter(
            Q(enrollment__student__first_name__icontains=q) | Q(enrollment__student__last_name__icontains=q)
            | Q(enrollment__student__username__icontains=q)
        )
    if form.value("verdict"):
        submissions = submissions.filter(verdict=form.value("verdict"))
    return submissions
