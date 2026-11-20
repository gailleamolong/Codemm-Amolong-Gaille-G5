from django.contrib import admin

from .models import Activity, Enrollment, LearningTrack

admin.site.register(LearningTrack)
admin.site.register(Activity)
admin.site.register(Enrollment)
