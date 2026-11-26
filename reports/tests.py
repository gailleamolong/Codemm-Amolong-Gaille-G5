import csv
import io

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from reviews.models import PeerReview
from tracks.models import Activity, Enrollment, LearningTrack, Submission, TestResult
from tracks.models import TestCase as ActivityTest
from tracks.tests import make_user

from .views import spreadsheet_safe


def submit(enrollment, activity, verdict, score, failed_test=None):
    attempt = Submission.objects.filter(enrollment=enrollment, activity=activity).count() + 1
    passed = 1 if verdict == "ACCEPTED" else 0
    submission = Submission.objects.create(enrollment=enrollment, activity=activity, attempt_no=attempt,
                                           source_code="x", verdict=verdict, passed_count=passed, total_count=1, score=score)
    if failed_test:
        TestResult.objects.create(submission=submission, test_case=failed_test, status="FAILED")
    return submission


class ReportTests(TestCase):
    def setUp(self):
        self.sir = make_user("sir", User.Role.INSTRUCTOR)
        self.track = LearningTrack.objects.create(instructor=self.sir, title="Python Basics", is_published=True)
        kw = dict(instructions="x", difficulty="EASY", language="PYTHON", is_published=True)
        self.sum = Activity.objects.create(track=self.track, title="Sum", **kw)
        self.loop = Activity.objects.create(track=self.track, title="Loop", **kw)
        test2 = ActivityTest.objects.create(activity=self.sum, seq_no=2, expected_output="5")
        self.ana = make_user("ana", User.Role.STUDENT)
        self.ben = make_user("=cmd", User.Role.STUDENT)
        ana_e = Enrollment.objects.create(student=self.ana, track=self.track)
        ben_e = Enrollment.objects.create(student=self.ben, track=self.track)
        submit(ana_e, self.sum, "WRONG_ANSWER", 50, failed_test=test2)
        accepted = submit(ana_e, self.sum, "ACCEPTED", 100)
        submit(ben_e, self.sum, "WRONG_ANSWER", 0, failed_test=test2)
        PeerReview.objects.create(submission=accepted, reviewer=self.ben, correctness_rating=5, readability_rating=5,
                                  approach_rating=5, comment="Clean and correct solution, well done.")

    def test_progress_report(self):
        self.client.force_login(self.sir)
        rows = {r["student"]: r for r in self.client.get(reverse("progress_report", args=[self.track.pk])).context["rows"]}
        self.assertEqual((rows[self.ana]["attempted"], rows[self.ana]["accepted"], rows[self.ana]["reviews_received"]), (1, 1, 1))
        self.assertEqual(rows[self.ana]["best_scores"], [100, None])
        self.assertEqual((rows[self.ben]["attempted"], rows[self.ben]["accepted"]), (1, 0))

    def test_pass_rate_summary(self):
        self.client.force_login(self.sir)
        rows = self.client.get(reverse("pass_rate_report", args=[self.track.pk])).context["rows"]
        summary = {r["activity"]: r for r in rows}
        self.assertEqual(
            (summary[self.sum]["attempted"], summary[self.sum]["accepted"], summary[self.sum]["pass_rate"],
             summary[self.sum]["average_attempts"], summary[self.sum]["most_failed"]),
            (2, 1, 50, 1.5, 2),
        )
        self.assertIsNone(summary[self.loop]["pass_rate"])

    def test_csv_exports_and_formula_guard(self):
        self.client.force_login(self.sir)
        response = self.client.get(reverse("progress_report", args=[self.track.pk]), {"format": "csv"})
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("python-basics-progress.csv", response["Content-Disposition"])
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(rows[0][:3], ["Student", "Status", "Attempted"])
        self.assertTrue(any(row[0].startswith("'=") for row in rows[1:]))
        pass_rate = self.client.get(reverse("pass_rate_report", args=[self.track.pk]), {"format": "csv"})
        self.assertIn("Most-failed test", pass_rate.content.decode())
        self.assertEqual((spreadsheet_safe("=1+1"), spreadsheet_safe("Ana"), spreadsheet_safe(None)), ("'=1+1", "Ana", ""))

    def test_student_sees_only_own_progress(self):
        self.client.force_login(self.ana)
        reports = self.client.get(reverse("my_progress")).context["reports"]
        self.assertEqual([r["row"]["student"] for r in reports], [self.ana])
        self.assertEqual(self.client.get(reverse("progress_report", args=[self.track.pk])).status_code, 403)

    def test_other_instructors_and_logged_out_users_are_blocked(self):
        self.client.force_login(make_user("other", User.Role.INSTRUCTOR))
        for name in ("progress_report", "pass_rate_report"):
            self.assertEqual(self.client.get(reverse(name, args=[self.track.pk]), {"format": "csv"}).status_code, 404)
        self.client.logout()
        url = reverse("progress_report", args=[self.track.pk])
        self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}")
