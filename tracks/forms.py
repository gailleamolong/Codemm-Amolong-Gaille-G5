from django import forms

from .models import Activity, LearningTrack


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
