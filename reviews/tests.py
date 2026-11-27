from unittest import mock

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from tracks.models import Activity, Enrollment, LearningTrack, Submission
from tracks.tests import make_user

from .forms import PeerReviewForm, ReflectionForm
from .models import PeerReview, Reflection

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

    def test_review_created_after_lookup_redirects_to_edit(self):
        def form_after_other_post(**kwargs):
            PeerReview.objects.create(submission=self.accepted, reviewer=self.ben, **REVIEW)
            return PeerReviewForm(**kwargs)

        with mock.patch("reviews.views.ReviewCreateView.form_class", side_effect=form_after_other_post):
            response = self.client.post(self.url, {**REVIEW, "approach_rating": 1})
        review = PeerReview.objects.get()
        self.assertEqual(review.approach_rating, REVIEW["approach_rating"])
        self.assertRedirects(response, reverse("review_update", args=[review.pk]))
        self.assertIn("You've already reviewed this submission. You can edit your review here.",
                      [str(m) for m in get_messages(response.wsgi_request)])

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

    def test_dropped_student_cannot_edit_or_delete_their_review(self):
        review = PeerReview.objects.create(submission=self.accepted, reviewer=self.ben, **REVIEW)
        self.ben_enrollment.status = Enrollment.Status.DROPPED
        self.ben_enrollment.save()
        self.assertEqual(self.client.post(reverse("review_update", args=[review.pk]), {**REVIEW, "approach_rating": 5}).status_code, 404)
        self.assertEqual(self.client.post(reverse("review_delete", args=[review.pk])).status_code, 404)
        review.refresh_from_db()
        self.assertEqual(review.approach_rating, 3)


TEXT = "I learned to read both numbers from one line and to test negative inputs."


class ReflectionTests(TestCase):
    def setUp(self):
        self.sir = make_user("sir", User.Role.INSTRUCTOR)
        track = LearningTrack.objects.create(instructor=self.sir, title="Python Basics", is_published=True)
        activity = Activity.objects.create(track=track, title="Sum", instructions="Add", difficulty="EASY",
                                           language="PYTHON", is_published=True)
        self.ana = make_user("ana", User.Role.STUDENT)
        self.submission = submit(Enrollment.objects.create(student=self.ana, track=track), activity, verdict="WRONG_ANSWER")
        self.url = reverse("reflection_create", args=[self.submission.pk])
        self.detail = reverse("submission_detail", args=[self.submission.pk])
        self.client.force_login(self.ana)

    def test_create_read_update_delete_reflection(self):
        response = self.client.post(self.url, {"content": TEXT})
        self.assertRedirects(response, self.detail)
        reflection = Reflection.objects.get()
        self.assertEqual(reflection.submission, self.submission)
        self.assertContains(self.client.get(self.detail), "negative inputs")

        self.client.force_login(self.sir)
        self.assertContains(self.client.get(self.detail), "negative inputs")

        self.client.force_login(self.ana)
        self.client.post(reverse("reflection_update", args=[reflection.pk]), {"content": TEXT + " Also edge cases."})
        reflection.refresh_from_db()
        self.assertTrue(reflection.content.endswith("edge cases."))
        self.client.post(reverse("reflection_delete", args=[reflection.pk]))
        self.assertFalse(Reflection.objects.exists())

    def test_content_must_be_at_least_50_characters(self):
        errors = self.client.post(self.url, {"content": "Too short."}).context["form"].errors
        self.assertIn("content", errors)
        self.assertFalse(Reflection.objects.exists())

    def test_only_one_reflection_per_submission(self):
        self.client.post(self.url, {"content": TEXT})
        response = self.client.post(self.url, {"content": TEXT + " again"})
        self.assertRedirects(response, reverse("reflection_update", args=[Reflection.objects.get().pk]))
        self.assertEqual(Reflection.objects.count(), 1)

    def test_reflection_created_after_lookup_redirects_to_edit(self):
        def form_after_other_post(**kwargs):
            Reflection.objects.create(submission=self.submission, content=TEXT)
            return ReflectionForm(**kwargs)

        with mock.patch("reviews.views.ReflectionCreateView.form_class", side_effect=form_after_other_post):
            response = self.client.post(self.url, {"content": TEXT + " More practice next time."})
        reflection = Reflection.objects.get()
        self.assertEqual(reflection.content, TEXT)
        self.assertRedirects(response, reverse("reflection_update", args=[reflection.pk]))
        self.assertIn("You've already written a reflection. You can edit it here.",
                      [str(m) for m in get_messages(response.wsgi_request)])

    def test_only_the_submitter_can_write_or_change_it(self):
        self.client.post(self.url, {"content": TEXT})
        reflection = Reflection.objects.get()
        self.client.force_login(make_user("ben", User.Role.STUDENT))
        self.assertEqual(self.client.post(self.url, {"content": TEXT}).status_code, 404)
        self.assertEqual(self.client.post(reverse("reflection_update", args=[reflection.pk]), {"content": TEXT}).status_code, 404)
        self.assertEqual(self.client.post(reverse("reflection_delete", args=[reflection.pk])).status_code, 404)
        self.client.force_login(self.sir)
        self.assertEqual(self.client.post(self.url, {"content": TEXT}).status_code, 403)
        self.client.logout()
        self.assertRedirects(self.client.get(self.url), f"{reverse('login')}?next={self.url}")
        self.assertEqual(Reflection.objects.get().content, TEXT)

