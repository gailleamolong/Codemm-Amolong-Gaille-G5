from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class User(AbstractUser):
    """The `users` table from the SDD data dictionary (Django custom user model).

    Passwords are hashed by Django's auth system and stored in `password_hash`.
    """

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrator"
        INSTRUCTOR = "INSTRUCTOR", "Instructor"
        STUDENT = "STUDENT", "Student"

    id = models.AutoField(primary_key=True, db_column="user_id")
    password = models.CharField("password", max_length=128, db_column="password_hash")
    email = models.EmailField("email address", max_length=254, unique=True)
    first_name = models.CharField("first name", max_length=50)
    last_name = models.CharField("last name", max_length=50)
    id_number = models.CharField(
        "ID number",
        max_length=15,
        unique=True,
        null=True,
        blank=True,
        validators=[RegexValidator(r"^[0-9][0-9-]{3,14}$", "Use digits and dashes only, e.g. 21-1234-567.")],
        help_text="Optional. Your CIT-U student or employee ID number, e.g. 21-1234-567.",
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    date_joined = models.DateTimeField("created at", default=timezone.now, db_column="created_at")

    class Meta:
        db_table = "users"
        constraints = [
            models.CheckConstraint(condition=Q(role__in=["ADMIN", "INSTRUCTOR", "STUDENT"]), name="users_role_check"),
        ]

    def save(self, *args, **kwargs):
        # Superusers created with `createsuperuser` are Codemm administrators.
        if self.is_superuser:
            self.role = self.Role.ADMIN
        # Store a blank ID number as NULL so UNIQUE allows many users without one.
        if not self.id_number:
            self.id_number = None
        super().save(*args, **kwargs)

    @property
    def dashboard_url_name(self):
        return {
            self.Role.ADMIN: "admin_dashboard",
            self.Role.INSTRUCTOR: "instructor_dashboard",
            self.Role.STUDENT: "student_dashboard",
        }[self.role]
