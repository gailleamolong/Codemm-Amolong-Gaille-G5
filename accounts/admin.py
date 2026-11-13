from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CodemmUserAdmin(UserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "id_number", "role", "is_active")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name", "id_number")
    fieldsets = UserAdmin.fieldsets + (("Codemm", {"fields": ("id_number", "role")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Codemm", {"fields": ("email", "first_name", "last_name", "id_number", "role")}),
    )
