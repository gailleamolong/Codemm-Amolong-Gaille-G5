from django.contrib.messages import get_messages
from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse

from accounts.models import User

from . import judge0
from .grading import same_output
from .models import Activity, Enrollment, LearningTrack, Submission
from .models import TestCase as ActivityTest


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
        self.assertContains(self.client.get(reverse("activity_create", args=[track.pk])), "New activity in Python Basics")
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


class TestCaseTests(TestCase):
    def setUp(self):
        self.instructor = make_user("sir", User.Role.INSTRUCTOR)
        self.track = LearningTrack.objects.create(instructor=self.instructor, title="Python Basics", is_published=True)
        self.activity = Activity.objects.create(track=self.track, **activity_data())
        self.client.force_login(self.instructor)

    def add(self, **overrides):
        data = {"seq_no": 1, "input_data": "2 3", "expected_output": "5", "points": 1}
        data.update(overrides)
        return self.client.post(reverse("test_case_create", args=[self.activity.pk]), data)

    def test_create_edit_delete(self):
        response = self.add(is_sample="on")
        self.assertRedirects(response, reverse("activity_detail", args=[self.activity.pk]))
        test = self.activity.test_cases.get()
        self.assertTrue(test.is_sample)
        self.assertContains(self.client.get(reverse("activity_detail", args=[self.activity.pk])), "Test 1")

        self.client.post(reverse("test_case_update", args=[test.pk]),
                         {"seq_no": 1, "input_data": "4 4", "expected_output": "8", "points": 2})
        test.refresh_from_db()
        self.assertEqual((test.expected_output, test.points, test.is_sample), ("8", 2, False))

        self.client.post(reverse("test_case_delete", args=[test.pk]))
        self.assertFalse(self.activity.test_cases.exists())

    def test_next_number_is_suggested(self):
        self.add()
        response = self.client.get(reverse("test_case_create", args=[self.activity.pk]))
        self.assertEqual(response.context["form"].initial["seq_no"], 2)

    def test_invalid_input(self):
        self.add()
        errors = self.add(expected_output="", points=0).context["form"].errors
        self.assertEqual(set(errors), {"seq_no", "expected_output", "points"})
        self.assertEqual(self.activity.test_cases.count(), 1)

    def test_login_required(self):
        self.client.logout()
        url = reverse("test_case_create", args=[self.activity.pk])
        self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}")

    def test_other_instructor_and_students_are_blocked(self):
        test = ActivityTest.objects.create(activity=self.activity, seq_no=1, expected_output="5")
        self.client.force_login(make_user("other", User.Role.INSTRUCTOR))
        self.assertEqual(self.add().status_code, 404)
        self.assertEqual(self.client.post(reverse("test_case_update", args=[test.pk]), {}).status_code, 404)
        self.assertEqual(self.client.post(reverse("test_case_delete", args=[test.pk])).status_code, 404)
        self.client.force_login(make_user("stud", User.Role.STUDENT))
        self.assertEqual(self.add().status_code, 403)
        self.assertTrue(ActivityTest.objects.filter(pk=test.pk).exists())

    def test_publishing_needs_a_test_case(self):
        url = reverse("activity_update", args=[self.activity.pk])
        errors = self.client.post(url, activity_data(is_published="on")).context["form"].errors
        self.assertEqual(errors["is_published"], ["Add at least one test case before publishing."])
        new = self.client.post(reverse("activity_create", args=[self.track.pk]), activity_data(title="New", is_published="on"))
        self.assertIn("is_published", new.context["form"].errors)

        self.add()
        self.client.post(url, activity_data(is_published="on"))
        self.activity.refresh_from_db()
        self.assertTrue(self.activity.is_published)

    def test_cannot_delete_last_test_case_of_published_activity(self):
        test = ActivityTest.objects.create(activity=self.activity, seq_no=1, expected_output="5")
        Activity.objects.filter(pk=self.activity.pk).update(is_published=True)
        response = self.client.post(reverse("test_case_delete", args=[test.pk]), follow=True)
        self.assertContains(response, "Unpublish the activity or add another test case first.")
        self.assertTrue(ActivityTest.objects.filter(pk=test.pk).exists())

    def test_students_see_samples_but_never_hidden_tests(self):
        ActivityTest.objects.create(activity=self.activity, seq_no=1, input_data="1 1", expected_output="SAMPLE-OUT", is_sample=True)
        ActivityTest.objects.create(activity=self.activity, seq_no=2, input_data="9 9", expected_output="HIDDEN-OUT")
        Activity.objects.filter(pk=self.activity.pk).update(is_published=True)
        student = make_user("ana", User.Role.STUDENT)
        Enrollment.objects.create(student=student, track=self.track)
        self.client.force_login(student)
        response = self.client.get(reverse("student_activity", args=[self.activity.pk]))
        self.assertContains(response, "SAMPLE-OUT")
        self.assertNotContains(response, "HIDDEN-OUT")


class SearchTests(TestCase):
    def setUp(self):
        self.sir = make_user("sir", User.Role.INSTRUCTOR)
        self.python = LearningTrack.objects.create(instructor=self.sir, title="Python Basics", description="Loops", is_published=True)
        self.java = LearningTrack.objects.create(instructor=self.sir, title="Java Intro", is_published=True)
        self.draft = LearningTrack.objects.create(instructor=self.sir, title="Draft C", is_published=False)
        Activity.objects.create(track=self.python, is_published=True, **activity_data())
        Activity.objects.create(track=self.python, is_published=True, **activity_data(title="Hard one", difficulty="HARD"))
        Activity.objects.create(track=self.java, is_published=True, **activity_data(title="Hello Java", language="JAVA"))
        self.student = make_user("ana", User.Role.STUDENT)

    def titles(self, response, key):
        return {str(item) for item in response.context[key]}

    def test_student_searches_and_filters_tracks(self):
        self.client.force_login(self.student)
        url = reverse("catalog")
        self.assertEqual(self.titles(self.client.get(url, {"q": "loops"}), "tracks"), {"Python Basics"})
        self.assertEqual(self.titles(self.client.get(url, {"language": "JAVA"}), "tracks"), {"Java Intro"})
        self.assertContains(self.client.get(url, {"q": "nothing-like-this"}), "No tracks match.")
        self.assertNotIn("Draft C", self.titles(self.client.get(url, {"q": "draft"}), "tracks"))

    def test_student_filters_activities_in_an_enrolled_track(self):
        Enrollment.objects.create(student=self.student, track=self.python)
        self.client.force_login(self.student)
        response = self.client.get(reverse("catalog_detail", args=[self.python.pk]), {"difficulty": "HARD"})
        self.assertEqual(self.titles(response, "activities"), {"Hard one"})

    def test_instructor_filters_own_tracks_and_activities(self):
        self.client.force_login(self.sir)
        drafts = self.client.get(reverse("track_list"), {"status": "draft"})
        self.assertEqual(self.titles(drafts, "tracks"), {"Draft C"})
        detail = self.client.get(reverse("track_detail", args=[self.python.pk]), {"q": "hard"})
        self.assertEqual(self.titles(detail, "activities"), {"Hard one"})

    def test_invalid_filter_shows_error_and_does_not_crash(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("catalog"), {"language": "COBOL"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "That filter isn")
        self.assertEqual(len(response.context["tracks"]), 2)

    def test_search_requires_login(self):
        url = reverse("catalog")
        self.assertRedirects(self.client.get(url, {"q": "x"}), f"{reverse('login')}?next={url}%3Fq%3Dx")


def outcome(status=judge0.ACCEPTED, stdout="", error="", time_ms=12):
    return {"status": status, "stdout": stdout, "error": error, "time_ms": time_ms}


@override_settings(JUDGE0_URL="https://judge0.test")
class SubmissionTests(TestCase):
    def setUp(self):
        self.sir = make_user("sir", User.Role.INSTRUCTOR)
        self.track = LearningTrack.objects.create(instructor=self.sir, title="Python Basics", is_published=True)
        self.activity = Activity.objects.create(track=self.track, is_published=True, **activity_data(max_attempts=3))
        self.sample = ActivityTest.objects.create(activity=self.activity, seq_no=1, input_data="2 3", expected_output="5", is_sample=True)
        self.hidden = ActivityTest.objects.create(activity=self.activity, seq_no=2, input_data="9 9", expected_output="SECRET-18", points=3)
        self.student = make_user("ana", User.Role.STUDENT)
        self.enrollment = Enrollment.objects.create(student=self.student, track=self.track)
        self.client.force_login(self.student)
        self.url = reverse("student_activity", args=[self.activity.pk])

    def submit(self, outcomes, code="a, b = map(int, input().split())\nprint(a + b)"):
        with mock.patch("tracks.judge0.run", side_effect=outcomes) as run:
            response = self.client.post(self.url, {"source_code": code})
        return response, run

    def test_accepted_submission_is_saved_with_results(self):
        response, run = self.submit([outcome(stdout="5\n"), outcome(stdout="SECRET-18")])
        submission = Submission.objects.get()
        self.assertRedirects(response, reverse("submission_detail", args=[submission.pk]))
        self.assertEqual((submission.verdict, submission.score, submission.passed_count, submission.attempt_no),
                         ("ACCEPTED", 100, 2, 1))
        self.assertEqual(submission.results.count(), 2)
        self.assertEqual(run.call_args_list[0].args, ("PYTHON", mock.ANY, "2 3", 2000))

    def test_partial_score_is_weighted_by_points(self):
        self.submit([outcome(stdout="5"), outcome(stdout="wrong")])
        submission = Submission.objects.get()
        self.assertEqual((submission.verdict, submission.score), ("WRONG_ANSWER", 25))

    def test_compilation_and_runtime_errors(self):
        self.submit([outcome(status=judge0.COMPILE_ERROR, error="SyntaxError")])
        self.submit([outcome(stdout="5"), outcome(status=7, error="ZeroDivisionError")])
        first, second = Submission.objects.order_by("attempt_no")
        self.assertEqual((first.verdict, first.score, first.results.count()), ("COMPILATION_ERROR", 0, 2))
        self.assertEqual((second.verdict, second.attempt_no), ("RUNTIME_ERROR", 2))

    def test_empty_code_is_rejected(self):
        response, run = self.submit([], code="   ")
        self.assertContains(response, "Write some code before submitting.")
        run.assert_not_called()
        self.assertFalse(Submission.objects.exists())

    def test_checker_failure_saves_nothing(self):
        response, _ = self.submit(judge0.Judge0Error("The code checker couldn't be reached. Try again in a minute."))
        self.assertContains(response, "couldn")
        self.assertFalse(Submission.objects.exists())

    @override_settings(JUDGE0_URL="")
    def test_submissions_closed_when_checker_is_off(self):
        self.assertContains(self.client.get(self.url), "Code checking isn")
        response, run = self.submit([outcome()])
        run.assert_not_called()
        self.assertFalse(Submission.objects.exists())

    def test_attempt_limit_and_due_date(self):
        Activity.objects.filter(pk=self.activity.pk).update(max_attempts=1)
        self.submit([outcome(stdout="5"), outcome(stdout="SECRET-18")])
        response, run = self.submit([outcome()])
        self.assertContains(response, "used all your attempts")
        Activity.objects.filter(pk=self.activity.pk).update(max_attempts=5, due_at=timezone.now() - timedelta(hours=1))
        response, run = self.submit([outcome()])
        self.assertContains(response, "due date has passed")
        run.assert_not_called()
        self.assertEqual(Submission.objects.count(), 1)

    def test_must_be_actively_enrolled_and_logged_in(self):
        self.enrollment.status = Enrollment.Status.DROPPED
        self.enrollment.save()
        response, run = self.submit([outcome()])
        self.assertEqual(response.status_code, 404)
        self.client.logout()
        self.assertRedirects(self.client.get(self.url), f"{reverse('login')}?next={self.url}")

    def test_hidden_test_details_stay_hidden_from_students(self):
        self.submit([outcome(stdout="5"), outcome(stdout="my-hidden-output")])
        detail = reverse("submission_detail", args=[Submission.objects.get().pk])
        student_view = self.client.get(detail)
        self.assertContains(student_view, "Hidden test 2")
        self.assertNotContains(student_view, "SECRET-18")
        self.assertNotContains(student_view, "my-hidden-output")
        self.client.force_login(self.sir)
        self.assertContains(self.client.get(detail), "SECRET-18")

    def test_others_cannot_open_a_submission(self):
        self.submit([outcome(stdout="5"), outcome(stdout="SECRET-18")])
        detail = reverse("submission_detail", args=[Submission.objects.get().pk])
        for other in (make_user("ben", User.Role.STUDENT), make_user("other", User.Role.INSTRUCTOR)):
            self.client.force_login(other)
            self.assertEqual(self.client.get(detail).status_code, 404)

    def test_records_with_submissions_cannot_be_deleted(self):
        self.submit([outcome(stdout="5"), outcome(stdout="SECRET-18")])
        self.client.force_login(self.sir)
        self.client.post(reverse("test_case_delete", args=[self.hidden.pk]))
        self.client.post(reverse("activity_delete", args=[self.activity.pk]))
        response = self.client.post(reverse("track_delete", args=[self.track.pk]), follow=True)
        self.assertContains(response, "Unpublish it instead")
        self.assertTrue(ActivityTest.objects.filter(pk=self.hidden.pk).exists())
        self.assertTrue(Activity.objects.filter(pk=self.activity.pk).exists())
        self.assertTrue(LearningTrack.objects.filter(pk=self.track.pk).exists())

    def test_output_comparison_ignores_trailing_spaces(self):
        self.assertTrue(same_output("5  \n\n", "5"))
        self.assertTrue(same_output("a \nb\n", "a\nb"))
        self.assertFalse(same_output("5 6", "56"))


@override_settings(JUDGE0_URL="https://judge0.test")
class Judge0ClientTests(TestCase):
    def fake_response(self, payload):
        import base64, io, json
        body = {**payload}
        for key in ("stdout", "stderr", "compile_output"):
            if body.get(key):
                body[key] = base64.b64encode(body[key].encode()).decode()
        response = io.BytesIO(json.dumps(body).encode())
        return mock.MagicMock(__enter__=lambda s: response, __exit__=lambda *a: None)

    def test_run_sends_code_and_reads_the_result(self):
        reply = self.fake_response({"status": {"id": 3}, "stdout": "5\n", "time": "0.012"})
        with mock.patch("urllib.request.urlopen", return_value=reply) as urlopen:
            result = judge0.run("PYTHON", "print(5)", "", 2000)
        request = urlopen.call_args.args[0]
        self.assertTrue(request.full_url.startswith("https://judge0.test/submissions?base64_encoded=true&wait=true"))
        self.assertEqual(result, {"status": 3, "stdout": "5\n", "error": "", "time_ms": 12})

    def test_unreachable_checker_and_internal_errors(self):
        import urllib.error
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            with self.assertRaises(judge0.Judge0Error):
                judge0.run("C", "int main(){}", "", 1000)
        with mock.patch("urllib.request.urlopen", return_value=self.fake_response({"status": {"id": 13}})):
            with self.assertRaises(judge0.Judge0Error):
                judge0.run("JAVA", "class Main {}", "", 1000)

    def test_requests_name_the_client(self):
        reply = self.fake_response({"status": {"id": 3}, "stdout": "5"})
        with mock.patch("urllib.request.urlopen", return_value=reply) as urlopen:
            judge0.run("PYTHON", "print(5)", "", 2000)
        self.assertEqual(urlopen.call_args.args[0].get_header("User-agent"), "Codemm/1.0")

    @override_settings(JUDGE0_URL="http://judge0.example.com")
    def test_plain_http_is_refused_so_code_is_never_sent_unencrypted(self):
        with mock.patch("urllib.request.urlopen") as urlopen, self.assertRaises(judge0.Judge0Error):
            judge0.run("PYTHON", "print(1)", "", 1000)
        urlopen.assert_not_called()

    @override_settings(JUDGE0_URL="http://localhost:2358")
    def test_plain_http_is_allowed_for_a_judge0_on_this_computer(self):
        with mock.patch("urllib.request.urlopen", return_value=self.fake_response({"status": {"id": 3}})):
            self.assertEqual(judge0.run("PYTHON", "print(1)", "", 1000)["status"], 3)

    def test_oversized_reply_is_rejected(self):
        huge = self.fake_response({"status": {"id": 3}, "stdout": "x" * (judge0.MAX_REPLY_BYTES + 10)})
        with mock.patch("urllib.request.urlopen", return_value=huge), self.assertRaises(judge0.Judge0Error):
            judge0.run("PYTHON", "print(1)", "", 1000)

    @override_settings(JUDGE0_URL="")
    def test_switched_off_checker_never_calls_out(self):
        with mock.patch("urllib.request.urlopen") as urlopen, self.assertRaises(judge0.Judge0Error):
            judge0.run("PYTHON", "print(1)", "", 1000)
        urlopen.assert_not_called()


@override_settings(JUDGE0_URL="https://judge0.test")
class RunCodeTests(TestCase):
    def setUp(self):
        sir = make_user("sir", User.Role.INSTRUCTOR)
        track = LearningTrack.objects.create(instructor=sir, title="Python Basics", is_published=True)
        self.activity = Activity.objects.create(track=track, is_published=True, **activity_data())
        ActivityTest.objects.create(activity=self.activity, seq_no=1, expected_output="5")
        self.student = make_user("ana", User.Role.STUDENT)
        Enrollment.objects.create(student=self.student, track=track)
        self.client.force_login(self.student)
        self.url = reverse("student_activity", args=[self.activity.pk])

    def run_code(self, result, code="print(input())", stdin="hello"):
        with mock.patch("tracks.judge0.run", side_effect=result) as run:
            response = self.client.post(self.url, {"action": "run", "source_code": code, "stdin": stdin})
        return response, run

    def test_run_shows_output_and_saves_nothing(self):
        response, run = self.run_code([outcome(stdout="hello\n")])
        self.assertContains(response, "Run · Finished")
        self.assertContains(response, "hello")
        run.assert_called_once_with("PYTHON", "print(input())", "hello", 2000)
        self.assertFalse(Submission.objects.exists())

    def test_run_reports_errors(self):
        response, _ = self.run_code([outcome(status=judge0.COMPILE_ERROR, error="SyntaxError: bad")])
        self.assertContains(response, "Compilation error")
        self.assertContains(response, "SyntaxError: bad")

    def test_run_does_not_use_attempts_or_care_about_the_limit(self):
        Activity.objects.filter(pk=self.activity.pk).update(max_attempts=1, due_at=timezone.now() - timedelta(days=1))
        response, run = self.run_code([outcome(stdout="ok")])
        run.assert_called_once()
        self.assertContains(response, "Run · Finished")

    def test_run_needs_code_and_a_working_checker(self):
        response, run = self.run_code([], code="")
        run.assert_not_called()
        self.assertContains(response, "This field is required.")
        response, _ = self.run_code(judge0.Judge0Error("The code checker couldn't be reached. Try again in a minute."))
        self.assertContains(response, "couldn")


@override_settings(JUDGE0_URL="https://judge0.test")
class SubmissionHistoryTests(TestCase):
    def setUp(self):
        self.sir = make_user("sir", User.Role.INSTRUCTOR)
        track = LearningTrack.objects.create(instructor=self.sir, title="Python Basics", is_published=True)
        self.activity = Activity.objects.create(track=track, is_published=True, **activity_data())
        ActivityTest.objects.create(activity=self.activity, seq_no=1, expected_output="5")
        self.ana = make_user("ana", User.Role.STUDENT)
        self.ben = make_user("ben", User.Role.STUDENT)
        for student, stdout in ((self.ana, "5"), (self.ben, "4")):
            Enrollment.objects.create(student=student, track=track)
            self.client.force_login(student)
            with mock.patch("tracks.judge0.run", return_value=outcome(stdout=stdout)):
                self.client.post(reverse("student_activity", args=[self.activity.pk]), {"source_code": "print(5)"})

    def test_instructor_sees_and_filters_submissions(self):
        self.client.force_login(self.sir)
        url = reverse("activity_detail", args=[self.activity.pk])
        response = self.client.get(url)
        self.assertEqual(len(response.context["submissions"]), 2)
        accepted = self.client.get(url, {"verdict": "ACCEPTED"}).context["submissions"]
        self.assertEqual([s.enrollment.student for s in accepted], [self.ana])
        by_name = self.client.get(url, {"q": "ben"}).context["submissions"]
        self.assertEqual([s.verdict for s in by_name], ["WRONG_ANSWER"])

    def test_student_dashboard_lists_only_own_attempts(self):
        self.client.force_login(self.ana)
        recent = self.client.get(reverse("student_dashboard")).context["recent"]
        self.assertEqual([s.enrollment.student for s in recent], [self.ana])


class DataIntegrityTests(TestCase):
    def setUp(self):
        self.sir = make_user("sir", User.Role.INSTRUCTOR)
        self.track = LearningTrack.objects.create(instructor=self.sir, title="Python Basics", is_published=True)
        self.client.force_login(self.sir)

    def due(self, **delta):
        return (timezone.localtime() + timedelta(**delta)).strftime("%Y-%m-%dT%H:%M")

    def test_due_date_cannot_be_in_the_past(self):
        url = reverse("activity_create", args=[self.track.pk])
        errors = self.client.post(url, activity_data(due_at=self.due(days=-1))).context["form"].errors
        self.assertEqual(errors["due_at"], ["Pick a due date in the future."])
        self.client.post(url, activity_data(due_at=self.due(days=7)))
        self.assertTrue(Activity.objects.filter(due_at__isnull=False).exists())

    def test_existing_past_due_date_can_be_kept_when_editing(self):
        past = timezone.localtime().replace(second=0, microsecond=0) - timedelta(days=1)
        activity = Activity.objects.create(track=self.track, due_at=past, **activity_data())
        response = self.client.post(reverse("activity_update", args=[activity.pk]),
                                    activity_data(title="Renamed", due_at=past.strftime("%Y-%m-%dT%H:%M")))
        self.assertRedirects(response, reverse("track_detail", args=[self.track.pk]))

    def count_track_page_queries(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as captured:
            self.client.get(reverse("track_detail", args=[self.track.pk]))
        return len(captured)

    def test_track_page_query_count_does_not_grow_with_students(self):
        for n in range(3):
            Enrollment.objects.create(student=make_user(f"s{n}", User.Role.STUDENT), track=self.track)
        with_three = self.count_track_page_queries()
        for n in range(3, 8):
            Enrollment.objects.create(student=make_user(f"s{n}", User.Role.STUDENT), track=self.track)
        self.assertEqual(self.count_track_page_queries(), with_three)

    def test_enrolling_twice_keeps_one_record(self):
        student = make_user("ana", User.Role.STUDENT)
        self.client.force_login(student)
        for _ in range(2):
            self.client.post(reverse("enroll", args=[self.track.pk]))
        self.assertEqual(Enrollment.objects.filter(student=student).count(), 1)


class SecurityTests(TestCase):
    def setUp(self):
        self.sir = make_user("sir", User.Role.INSTRUCTOR)
        self.track = LearningTrack.objects.create(instructor=self.sir, title="Python Basics", is_published=True)

    def test_post_without_csrf_token_is_rejected(self):
        client = self.client_class(enforce_csrf_checks=True)
        client.force_login(self.sir)
        self.assertEqual(client.post(reverse("track_create"), {"title": "No token"}).status_code, 403)
        self.assertEqual(client.post(reverse("track_delete", args=[self.track.pk])).status_code, 403)
        self.assertFalse(LearningTrack.objects.filter(title="No token").exists())
        self.assertTrue(LearningTrack.objects.filter(pk=self.track.pk).exists())

    def test_delete_pages_ask_before_deleting(self):
        self.client.force_login(self.sir)
        response = self.client.get(reverse("track_delete", args=[self.track.pk]))
        self.assertContains(response, "This can't be undone.")
        self.assertTrue(LearningTrack.objects.filter(pk=self.track.pk).exists())

    def test_user_input_is_escaped_not_run(self):
        self.client.force_login(self.sir)
        self.client.post(reverse("track_update", args=[self.track.pk]), {"title": "<script>alert(1)</script>"})
        response = self.client.get(reverse("track_detail", args=[self.track.pk]))
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_student_cannot_reach_instructor_pages_by_url(self):
        self.client.force_login(make_user("ana", User.Role.STUDENT))
        for name in ("track_list", "track_create"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)
        for name in ("track_detail", "track_update", "track_delete", "progress_report"):
            self.assertEqual(self.client.get(reverse(name, args=[self.track.pk])).status_code, 403)


class PublishErrorMessageTests(TestCase):
    def test_publish_error_is_shown_on_the_page(self):
        sir = make_user("sir", User.Role.INSTRUCTOR)
        track = LearningTrack.objects.create(instructor=sir, title="Python Basics")
        self.client.force_login(sir)
        response = self.client.post(reverse("activity_create", args=[track.pk]), activity_data(is_published="on"))
        self.assertContains(response, "Add at least one test case before publishing.")


@override_settings(JUDGE0_URL="https://judge0.test")
class CodeCheckRateLimitTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        sir = make_user("sir", User.Role.INSTRUCTOR)
        track = LearningTrack.objects.create(instructor=sir, title="Python Basics", is_published=True)
        self.activity = Activity.objects.create(track=track, is_published=True, **activity_data(max_attempts=50))
        ActivityTest.objects.create(activity=self.activity, seq_no=1, expected_output="5")
        self.student = make_user("ana", User.Role.STUDENT)
        Enrollment.objects.create(student=self.student, track=track)
        self.client.force_login(self.student)
        self.url = reverse("student_activity", args=[self.activity.pk])

    def test_more_than_ten_runs_a_minute_are_refused(self):
        with mock.patch("tracks.judge0.run", return_value=outcome(stdout="5")) as run:
            for _ in range(10):
                self.client.post(self.url, {"action": "run", "source_code": "print(5)", "stdin": ""})
            response = self.client.post(self.url, {"action": "run", "source_code": "print(5)", "stdin": ""})
        self.assertContains(response, "You&#x27;re running code too often. Wait a minute and try again.")
        self.assertEqual(run.call_count, 10)

    def test_submits_count_toward_the_same_limit_and_save_nothing_when_refused(self):
        with mock.patch("tracks.judge0.run", return_value=outcome(stdout="5")):
            for _ in range(10):
                self.client.post(self.url, {"action": "submit", "source_code": "print(5)"})
            self.client.post(self.url, {"action": "submit", "source_code": "print(5)"})
        self.assertEqual(Submission.objects.count(), 10)

    def test_the_limit_is_per_student(self):
        other = make_user("ben", User.Role.STUDENT)
        Enrollment.objects.create(student=other, track=self.activity.track)
        with mock.patch("tracks.judge0.run", return_value=outcome(stdout="5")) as run:
            for _ in range(10):
                self.client.post(self.url, {"action": "run", "source_code": "print(5)", "stdin": ""})
            self.client.force_login(other)
            self.client.post(self.url, {"action": "run", "source_code": "print(5)", "stdin": ""})
        self.assertEqual(run.call_count, 11)
