from django.contrib import admin

from .models import Activity, Enrollment, LearningTrack, TestCase

admin.site.register(LearningTrack)
admin.site.register(Activity)
admin.site.register(Enrollment)
admin.site.register(TestCase)
