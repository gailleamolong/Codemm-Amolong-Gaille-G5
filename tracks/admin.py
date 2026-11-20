from django.contrib import admin

from .models import Activity, LearningTrack

admin.site.register(LearningTrack)
admin.site.register(Activity)
