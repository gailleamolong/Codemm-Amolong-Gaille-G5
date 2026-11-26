from django.contrib import admin

from .models import Activity, Enrollment, LearningTrack, Submission, TestCase, TestResult

admin.site.register(LearningTrack)
admin.site.register(Activity)
admin.site.register(Enrollment)
admin.site.register(TestCase)
admin.site.register(Submission)
admin.site.register(TestResult)
