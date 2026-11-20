from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .models import Activity, Enrollment, LearningTrack


def make_user(username, role):
    return User.objects.create_user(username, f"{username}@example.com", "Str0ng-pass-123", role=role,
                                    first_name=username.title(), last_name="Tester")


def activity_data(**overrides):
    data = {"title": "Sum of two numbers", "instructions": "Read two integers and print their sum.",
            "difficulty": "EASY", "language": "PYTHON", "time_limit_ms": 2000, "max_attempts": 10}
    data.update(overrides)
    return data


class TrackCrudTests(TestCase):
    def setUp(self):
        self.instructor = make_user("sir", User.Role.INSTRUCTOR)
        self.client.force_login(self.instructor)

    def test_create_read_update_delete_track(self):
        response = self.client.post(reverse("track_create"), {"title": "Python Basics", "description": "Intro"})
        track = LearningTrack.objects.get()
        self.assertEqual(track.instructor, self.instructor)
        self.assertRedirects(response, reverse("track_detail", args=[track.pk]))
        self.assertIn("Track created.", [str(m) for m in get_messages(response.wsgi_request)])

        self.assertContains(self.client.get(reverse("track_list")), "Python Basics")

        self.client.post(reverse("track_update", args=[track.pk]), {"title": "Python 1", "is_published": "on"})
        track.refresh_from_db()
        self.assertEqual(track.title, "Python 1")
        self.assertTrue(track.is_published)

        self.client.post(reverse("track_delete", args=[track.pk]))
        self.assertFalse(LearningTrack.objects.exists())

    def test_title_required_and_unique_per_instructor(self):
        self.assertIn("title", self.client.post(reverse("track_create"), {"title": ""}).context["form"].errors)
        LearningTrack.objects.create(instructor=self.instructor, title="Loops")
        response = self.client.post(reverse("track_create"), {"title": "loops"})
        self.assertEqual(response.context["form"].errors["title"], ["You already have a track with this title."])

    def test_activity_crud_and_validation(self):
        track = LearningTrack.objects.create(instructor=self.instructor, title="Python Basics")
        self.client.post(reverse("activity_create", args=[track.pk]), activity_data())
        activity = Activity.objects.get()
        self.assertEqual(activity.track, track)
        self.assertContains(self.client.get(reverse("activity_detail", args=[activity.pk])), "Read two integers")

        self.client.post(reverse("activity_update", args=[activity.pk]), activity_data(difficulty="HARD"))
        activity.refresh_from_db()
        self.assertEqual(activity.difficulty, "HARD")

        errors = self.client.post(
            reverse("activity_create", args=[track.pk]),
            activity_data(title="Other", time_limit_ms=100, max_attempts=99, language="RUBY"),
        ).context["form"].errors
        self.assertEqual(set(errors), {"time_limit_ms", "max_attempts", "language"})

        self.client.post(reverse("activity_delete", args=[activity.pk]))
        self.assertFalse(Activity.objects.exists())


class TrackAccessTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner", User.Role.INSTRUCTOR)
        self.other = make_user("other", User.Role.INSTRUCTOR)
        self.student = make_user("stud", User.Role.STUDENT)
        self.track = LearningTrack.objects.create(instructor=self.owner, title="Python Basics")
        self.activity = Activity.objects.create(track=self.track, **activity_data())

    def test_logged_out_users_go_to_login(self):
        url = reverse("track_list")
        self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}")

    def test_students_cannot_manage_tracks(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("track_create")).status_code, 403)
        self.assertEqual(self.client.post(reverse("track_delete", args=[self.track.pk])).status_code, 403)

    def test_instructors_cannot_touch_other_instructors_tracks(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("track_detail", args=[self.track.pk])).status_code, 404)
        for name, pk in [("track_update", self.track.pk), ("track_delete", self.track.pk),
                         ("activity_create", self.track.pk), ("activity_update", self.activity.pk),
                         ("activity_delete", self.activity.pk)]:
            self.assertEqual(self.client.post(reverse(name, args=[pk]), activity_data(title="Hack")).status_code, 404, name)
        self.assertTrue(LearningTrack.objects.filter(pk=self.track.pk).exists())
        self.assertNotContains(self.client.get(reverse("track_list")), "Python Basics")

    def test_tracks_show_on_instructor_dashboard(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("instructor_dashboard")), "Python Basics")


class EnrollmentTests(TestCase):
    def setUp(self):
        self.instructor = make_user("sir", User.Role.INSTRUCTOR)
        self.student = make_user("ana", User.Role.STUDENT)
        self.track = LearningTrack.objects.create(instructor=self.instructor, title="Python Basics", is_published=True)
        self.draft = LearningTrack.objects.create(instructor=self.instructor, title="Secret Draft")
        self.activity = Activity.objects.create(track=self.track, is_published=True, **activity_data())
        self.client.force_login(self.student)

    def test_catalog_shows_only_published_tracks(self):
        response = self.client.get(reverse("catalog"))
        self.assertContains(response, "Python Basics")
        self.assertNotContains(response, "Secret Draft")
        self.assertEqual(self.client.get(reverse("catalog_detail", args=[self.draft.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("enroll", args=[self.draft.pk])).status_code, 404)

    def test_enroll_see_activities_drop_and_rejoin(self):
        detail = reverse("catalog_detail", args=[self.track.pk])
        activity_url = reverse("student_activity", args=[self.activity.pk])
        self.assertNotContains(self.client.get(detail), "Sum of two numbers")
        self.assertEqual(self.client.get(activity_url).status_code, 404)

        response = self.client.post(reverse("enroll", args=[self.track.pk]))
        self.assertRedirects(response, detail)
        enrollment = Enrollment.objects.get(student=self.student, track=self.track)
        self.assertEqual(enrollment.status, Enrollment.Status.ACTIVE)
        self.assertContains(self.client.get(detail), "Sum of two numbers")
        self.assertContains(self.client.get(activity_url), "Read two integers")
        self.assertContains(self.client.get(reverse("student_dashboard")), "Python Basics")

        again = self.client.post(reverse("enroll", args=[self.track.pk]), follow=True)
        self.assertContains(again, "already enrolled")
        self.assertEqual(Enrollment.objects.count(), 1)

        self.client.post(reverse("drop", args=[self.track.pk]))
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, Enrollment.Status.DROPPED)
        self.assertEqual(self.client.get(activity_url).status_code, 404)

        self.client.post(reverse("enroll", args=[self.track.pk]))
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, Enrollment.Status.ACTIVE)

    def test_instructor_sees_enrolled_students_and_cannot_enroll(self):
        Enrollment.objects.create(student=self.student, track=self.track)
        self.client.force_login(self.instructor)
        self.assertContains(self.client.get(reverse("track_detail", args=[self.track.pk])), "Ana Tester")
        self.assertEqual(self.client.post(reverse("enroll", args=[self.track.pk])).status_code, 403)
