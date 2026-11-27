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
