from django.test import RequestFactory, TestCase
from django.views.defaults import server_error

from accounts.models import User
from tracks.tests import make_user


class ErrorPageTests(TestCase):
    def test_unknown_url_shows_the_custom_404_page(self):
        response = self.client.get("/no-such-page/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Page not found", status_code=404)
        self.assertNotContains(response, "Traceback", status_code=404)

    def test_invalid_ids_show_404_instead_of_crashing(self):
        self.client.force_login(make_user("sir", User.Role.INSTRUCTOR))
        for url in ("/tracks/999999/", "/tracks/activities/999999/", "/tracks/tests/999999/edit/",
                    "/tracks/submissions/999999/", "/reports/tracks/999999/progress/"):
            self.assertContains(self.client.get(url), "Page not found", status_code=404)

    def test_server_error_shows_the_custom_500_page(self):
        response = server_error(RequestFactory().get("/"))
        self.assertEqual(response.status_code, 500)
        self.assertIn("Something went wrong", response.content.decode())
        self.assertNotIn("Traceback", response.content.decode())


class StudentDashboardTests(TestCase):
    def test_recent_attempts_show_on_the_page_not_in_the_title(self):
        from tracks.models import Activity, Enrollment, LearningTrack, Submission
        from tracks.tests import activity_data
        sir = make_user("sir", User.Role.INSTRUCTOR)
        track = LearningTrack.objects.create(instructor=sir, title="Python Basics", is_published=True)
        activity = Activity.objects.create(track=track, is_published=True, **activity_data())
        student = make_user("ana", User.Role.STUDENT)
        enrollment = Enrollment.objects.create(student=student, track=track)
        Submission.objects.create(enrollment=enrollment, activity=activity, attempt_no=1, source_code="print(5)",
                                  verdict=Submission.Verdict.ACCEPTED, passed_count=1, total_count=1, score=100)
        self.client.force_login(student)
        html = self.client.get("/student/").content.decode()
        title = html.split("<title>")[1].split("</title>")[0]
        self.assertNotIn("Recent attempts", title)
        self.assertIn("Recent attempts", html.split('id="content"')[1])


class UserEditPageTests(TestCase):
    def test_nav_belongs_to_the_admin_not_the_user_being_edited(self):
        admin = make_user("boss", User.Role.ADMIN)
        student = make_user("ana", User.Role.STUDENT)
        self.client.force_login(admin)
        response = self.client.get(f"/administrator/users/{student.pk}/")
        self.assertEqual(response.context["user"], admin)
        self.assertNotContains(response, "my-progress")


class TrackOwnerRoleTests(TestCase):
    def setUp(self):
        from tracks.models import LearningTrack
        self.sir = make_user("sir", User.Role.INSTRUCTOR)
        self.track = LearningTrack(instructor=self.sir, title="Python Basics")
        self.track.save()

    def test_admin_cannot_change_the_role_of_an_instructor_who_owns_tracks(self):
        self.client.force_login(make_user("boss", User.Role.ADMIN))
        response = self.client.post(f"/administrator/users/{self.sir.pk}/", {"role": "STUDENT", "is_active": "on"})
        self.assertContains(response, "owns learning tracks")
        self.sir.refresh_from_db()
        self.assertEqual(self.sir.role, User.Role.INSTRUCTOR)

    def test_a_track_owner_must_be_an_instructor(self):
        from django.core.exceptions import ValidationError
        self.track.instructor = make_user("ana", User.Role.STUDENT)
        with self.assertRaises(ValidationError):
            self.track.full_clean()


class ExpiredFormPageTests(TestCase):
    def test_a_stale_form_shows_a_friendly_page_with_a_way_back(self):
        from django.test import Client
        response = Client(enforce_csrf_checks=True).post("/accounts/login/", {"username": "x", "password": "y"})
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "This page expired", status_code=403)
        self.assertNotContains(response, "CSRF verification failed", status_code=403)
