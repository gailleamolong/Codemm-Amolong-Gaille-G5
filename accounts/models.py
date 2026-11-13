from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Codemm user (ERD: USER). Passwords are hashed by Django's auth system."""

    class Role(models.TextChoices):
        LEARNER = "LEARNER", "Learner"
        INSTRUCTOR = "INSTRUCTOR", "Instructor-consultant"
        ADMIN = "ADMIN", "Administrator"

    email = models.EmailField("email address", unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.LEARNER)
    contact_number = models.CharField(max_length=20, blank=True)

    class Meta:
        db_table = "tbluser"

    def save(self, *args, **kwargs):
        # Superusers created with `createsuperuser` are Codemm administrators.
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def dashboard_url_name(self):
        return {
            self.Role.LEARNER: "learner_dashboard",
            self.Role.INSTRUCTOR: "instructor_dashboard",
            self.Role.ADMIN: "admin_dashboard",
        }[self.role]
