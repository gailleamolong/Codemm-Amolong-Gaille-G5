from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from tracks.models import Activity, Enrollment, LearningTrack, Submission
from tracks.tests import make_user

from .models import PeerReview

def submit(enrollment, activity, verdict="ACCEPTED"):
    attempt = Submission.objects.filter(enrollment=enrollment, activity=activity).count() + 1
    passed = 1 if verdict == "ACCEPTED" else 0
    return Submission.objects.create(enrollment=enrollment, activity=activity, attempt_no=attempt,
                                     source_code="print(5)", verdict=verdict, passed_count=passed,
                                     total_count=1, score=100 * passed)


REVIEW = {"correctness_rating": 5, "readability_rating": 4, "approach_rating": 3,
          "comment": "Clear names and a simple loop, nice work."}


class PeerReviewTests(TestCase):
    def setUp(self):
        sir = make_user("sir", User.Role.INSTRUCTOR)
        self.track = LearningTrack.objects.create(instructor=sir, title="Python Basics", is_published=True)
        self.activity = Activity.objects.create(track=self.track, title="Sum", instructions="Add", difficulty="EASY",
                                                language="PYTHON", is_published=True)
        self.ana = make_user("ana", User.Role.STUDENT)
        self.ben = make_user("ben", User.Role.STUDENT)
        self.ana_enrollment = Enrollment.objects.create(student=self.ana, track=self.track)
        self.ben_enrollment = Enrollment.objects.create(student=self.ben, track=self.track)
        self.accepted = submit(self.ana_enrollment, self.activity)
        self.url = reverse("review_create", args=[self.accepted.pk])
        self.client.force_login(self.ben)

    def test_create_read_update_delete_review(self):
        response = self.client.post(self.url, REVIEW)
        self.assertRedirects(response, reverse("student_activity", args=[self.activity.pk]))
        review = PeerReview.objects.get()
        self.assertEqual((review.reviewer, review.submission, review.correctness_rating), (self.ben, self.accepted, 5))
        self.assertIn("Review posted.", [str(m) for m in get_messages(response.wsgi_request)])

        self.client.force_login(self.ana)
        self.assertContains(self.client.get(reverse("submission_detail", args=[self.accepted.pk])), "Clear names")

        self.client.force_login(self.ben)
        self.client.post(reverse("review_update", args=[review.pk]), {**REVIEW, "approach_rating": 5})
        review.refresh_from_db()
        self.assertEqual(review.approach_rating, 5)
        self.client.post(reverse("review_delete", args=[review.pk]))
        self.assertFalse(PeerReview.objects.exists())

    def test_invalid_ratings_and_short_comment(self):
        errors = self.client.post(self.url, {**REVIEW, "correctness_rating": 9, "comment": "ok"}).context["form"].errors
        self.assertEqual(set(errors), {"correctness_rating", "comment"})
        self.assertFalse(PeerReview.objects.exists())

    def test_only_one_review_per_submission(self):
        self.client.post(self.url, REVIEW)
        response = self.client.post(self.url, {**REVIEW, "comment": "A second review that should not be saved."})
        self.assertRedirects(response, reverse("review_update", args=[PeerReview.objects.get().pk]))
        self.assertEqual(PeerReview.objects.count(), 1)

    def test_cannot_review_own_unaccepted_or_other_track_submissions(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.client.post(self.url, REVIEW).status_code, 404)
        self.client.force_login(self.ben)
        wrong = submit(self.ben_enrollment, self.activity, verdict="WRONG_ANSWER")
        self.client.force_login(self.ana)
        self.assertEqual(self.client.post(reverse("review_create", args=[wrong.pk]), REVIEW).status_code, 404)
        outsider = make_user("cara", User.Role.STUDENT)
        self.client.force_login(outsider)
        self.assertEqual(self.client.post(self.url, REVIEW).status_code, 404)
        self.ben_enrollment.status = Enrollment.Status.DROPPED
        self.ben_enrollment.save()
        self.client.force_login(self.ben)
        self.assertEqual(self.client.post(self.url, REVIEW).status_code, 404)
        self.assertFalse(PeerReview.objects.exists())

    def test_login_required_and_instructors_cannot_review(self):
        self.client.logout()
        self.assertRedirects(self.client.get(self.url), f"{reverse('login')}?next={self.url}")
        self.client.force_login(User.objects.get(username="sir"))
        self.assertEqual(self.client.post(self.url, REVIEW).status_code, 403)

    def test_cannot_edit_or_delete_someone_elses_review(self):
        self.client.post(self.url, REVIEW)
        review = PeerReview.objects.get()
        self.client.force_login(make_user("cara", User.Role.STUDENT))
        self.assertEqual(self.client.post(reverse("review_update", args=[review.pk]), REVIEW).status_code, 404)
        self.assertEqual(self.client.post(reverse("review_delete", args=[review.pk])).status_code, 404)
        self.assertTrue(PeerReview.objects.filter(pk=review.pk).exists())

    def test_activity_page_lists_solutions_to_review(self):
        response = self.client.get(reverse("student_activity", args=[self.activity.pk]))
        self.assertEqual([s for s, _ in response.context["to_review"]], [self.accepted])
