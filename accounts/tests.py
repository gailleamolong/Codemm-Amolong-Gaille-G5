from django.contrib.messages import get_messages
from django.db import IntegrityError, connection
from django.test import TestCase
from django.urls import reverse

from .models import User

PASSWORD = "Str0ng-pass-123"


def make_user(username, role=User.Role.STUDENT, **extra):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password=PASSWORD,
        first_name=username.title(),
        last_name="Tester",
        role=role,
        **extra,
    )


def messages_of(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


class UsersTableTests(TestCase):
    """The `users` table follows the SDD data dictionary."""

    def test_table_and_column_names(self):
        with connection.cursor() as cursor:
            columns = {c.name for c in connection.introspection.get_table_description(cursor, "users")}
        for column in ("user_id", "username", "email", "password_hash", "first_name", "last_name",
                       "id_number", "role", "is_active", "created_at"):
            self.assertIn(column, columns)

    def test_role_check_constraint(self):
        user = make_user("ana")
        with self.assertRaises(IntegrityError):
            User.objects.filter(pk=user.pk).update(role="GUEST")


class RegistrationTests(TestCase):
    def payload(self, **overrides):
        data = {
            "username": "juan",
            "first_name": "Juan",
            "last_name": "Dela Cruz",
            "email": "juan@example.com",
            "id_number": "21-1234-567",
            "password1": PASSWORD,
            "password2": PASSWORD,
        }
        data.update(overrides)
        return data

    def test_register_creates_student_with_hashed_password(self):
        response = self.client.post(reverse("register"), self.payload())
        self.assertRedirects(response, reverse("login"))
        user = User.objects.get(username="juan")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertTrue(user.check_password(PASSWORD))
        self.assertIn("Account created for juan. You can now log in.", messages_of(response))

    def test_id_number_is_optional(self):
        self.client.post(reverse("register"), self.payload(id_number=""))
        self.client.post(reverse("register"), self.payload(username="pedro", email="pedro@example.com", id_number=""))
        self.assertEqual(User.objects.filter(id_number__isnull=True).count(), 2)

    def test_required_fields(self):
        response = self.client.post(reverse("register"), {})
        form = response.context["form"]
        for field in ("username", "first_name", "last_name", "email", "password1", "password2"):
            self.assertIn(field, form.errors)
        self.assertIn("Please fix the errors below.", messages_of(response))

    def test_invalid_email_format(self):
        response = self.client.post(reverse("register"), self.payload(email="not-an-email"))
        self.assertIn("email", response.context["form"].errors)
        self.assertFalse(User.objects.exists())

    def test_duplicate_username_email_and_id_number_rejected(self):
        make_user("juan", id_number="21-1234-567")
        response = self.client.post(reverse("register"), self.payload(email="JUAN@example.com"))
        errors = response.context["form"].errors
        self.assertIn("username", errors)
        self.assertEqual(errors["email"], ["An account with this email already exists."])
        self.assertIn("id_number", errors)
        self.assertEqual(User.objects.count(), 1)

    def test_password_confirmation_must_match(self):
        response = self.client.post(reverse("register"), self.payload(password2="Different-pass-456"))
        self.assertIn("password2", response.context["form"].errors)
        self.assertFalse(User.objects.exists())

    def test_cannot_choose_own_role(self):
        self.client.post(reverse("register"), self.payload(role=User.Role.ADMIN))
        self.assertEqual(User.objects.get(username="juan").role, User.Role.STUDENT)


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.user = make_user("maria")

    def test_login_redirects_to_role_dashboard(self):
        response = self.client.post(reverse("login"), {"username": "maria", "password": PASSWORD}, follow=True)
        self.assertRedirects(response, reverse("student_dashboard"))

    def test_login_with_email(self):
        response = self.client.post(reverse("login"), {"username": "MARIA@example.com", "password": PASSWORD})
        self.assertRedirects(response, reverse("dashboard"), target_status_code=302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_invalid_credentials_show_error(self):
        response = self.client.post(reverse("login"), {"username": "maria", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Incorrect username, email or password.", messages_of(response))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_deactivated_user_cannot_log_in(self):
        self.user.is_active = False
        self.user.save()
        self.client.post(reverse("login"), {"username": "maria", "password": PASSWORD})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_ends_session(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)

    def test_protected_pages_redirect_to_login(self):
        names = ("dashboard", "student_dashboard", "instructor_dashboard", "admin_dashboard", "profile", "profile_edit")
        for name in names:
            url = reverse(name)
            self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}")


class RoleDashboardTests(TestCase):
    def setUp(self):
        self.users = {
            "student_dashboard": make_user("student", User.Role.STUDENT),
            "instructor_dashboard": make_user("instructor", User.Role.INSTRUCTOR),
            "admin_dashboard": User.objects.create_superuser("boss", "boss@example.com", PASSWORD),
        }

    def test_superuser_is_admin_role(self):
        self.assertEqual(self.users["admin_dashboard"].role, User.Role.ADMIN)

    def test_each_role_reaches_only_its_own_dashboard(self):
        for own, user in self.users.items():
            self.client.force_login(user)
            self.assertRedirects(self.client.get(reverse("dashboard")), reverse(own))
            for name in self.users:
                expected = 200 if name == own else 403
                self.assertEqual(self.client.get(reverse(name)).status_code, expected, f"{user.username} -> {name}")

    def test_admin_dashboard_lists_all_users(self):
        self.client.force_login(self.users["admin_dashboard"])
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(len(response.context["rows"]), 3)
        self.assertContains(response, "student@example.com")


class AdminUserManagementTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin1", User.Role.ADMIN)
        self.student = make_user("carlo")
        self.url = reverse("admin_update_user", args=[self.student.pk])
        self.prefix = f"u{self.student.pk}"

    def test_admin_assigns_role_and_deactivates(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, {f"{self.prefix}-role": User.Role.INSTRUCTOR})
        self.student.refresh_from_db()
        self.assertEqual(self.student.role, User.Role.INSTRUCTOR)
        self.assertFalse(self.student.is_active)

    def test_non_admin_cannot_change_roles(self):
        self.client.force_login(self.student)
        response = self.client.post(self.url, {f"{self.prefix}-role": User.Role.ADMIN, f"{self.prefix}-is_active": "on"})
        self.assertEqual(response.status_code, 403)
        self.student.refresh_from_db()
        self.assertEqual(self.student.role, User.Role.STUDENT)

    def test_admin_cannot_change_own_account(self):
        self.client.force_login(self.admin)
        prefix = f"u{self.admin.pk}"
        self.client.post(reverse("admin_update_user", args=[self.admin.pk]), {f"{prefix}-role": User.Role.STUDENT})
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, User.Role.ADMIN)
        self.assertTrue(self.admin.is_active)


class ProfileTests(TestCase):
    def setUp(self):
        self.user = make_user("ana")
        self.other = make_user("ben", id_number="22-0000-001")
        self.client.force_login(self.user)

    def form(self, **overrides):
        data = {"first_name": "Ana", "last_name": "Santos", "email": "ana@example.com", "id_number": ""}
        data.update(overrides)
        return data

    def test_profile_shows_own_details(self):
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "ana@example.com")
        self.assertNotContains(response, "ben@example.com")

    def test_update_profile(self):
        response = self.client.post(
            reverse("profile_edit"), self.form(last_name="Reyes", email="ana.reyes@example.com", id_number="21-5555-123")
        )
        self.assertRedirects(response, reverse("profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, "Reyes")
        self.assertEqual(self.user.email, "ana.reyes@example.com")
        self.assertEqual(self.user.id_number, "21-5555-123")
        self.assertIn("Your profile has been updated.", messages_of(response))

    def test_cannot_take_another_users_email_or_id_number(self):
        response = self.client.post(reverse("profile_edit"), self.form(email="BEN@example.com", id_number="22-0000-001"))
        errors = response.context["form"].errors
        self.assertIn("email", errors)
        self.assertIn("id_number", errors)

    def test_edit_ignores_role_and_other_users(self):
        self.client.post(reverse("profile_edit"), self.form(role=User.Role.ADMIN, id=self.other.pk))
        self.user.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.STUDENT)
        self.assertEqual(self.other.email, "ben@example.com")

    def test_invalid_id_number(self):
        response = self.client.post(reverse("profile_edit"), self.form(id_number="abc"))
        self.assertIn("id_number", response.context["form"].errors)
