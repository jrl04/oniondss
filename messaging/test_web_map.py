from contextlib import closing
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.utils import timezone


class StaffMapTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user("map-officer", is_staff=True)

    def test_interactive_requests_extend_session_but_background_poll_does_not(self):
        self.client.force_login(self.staff)
        session = Session.objects.get(session_key=self.client.session.session_key)
        near_expiry = timezone.now() + timedelta(minutes=2)
        Session.objects.filter(pk=session.pk).update(expire_date=near_expiry)

        self.assertEqual(self.client.get("/api/conversations/", HTTP_X_DSS_BACKGROUND="1").status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.expire_date, near_expiry)

        self.assertEqual(self.client.get("/fields/map/").status_code, 200)
        session.refresh_from_db()
        self.assertGreater(session.expire_date, near_expiry)

        Session.objects.filter(pk=session.pk).update(expire_date=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get("/fields/map/").status_code, 302)

    def test_geojson_layers_are_discovered_and_streamed_to_staff_only(self):
        content = b'{"type":"FeatureCollection","features":[]}'
        with TemporaryDirectory() as directory:
            layer_dir = Path(directory)
            (layer_dir / "soil.geojson").write_bytes(content)
            with self.settings(MAP_GEOJSON_DIR=layer_dir):
                url = "/fields/map/layers/soil/"
                self.assertEqual(self.client.get(url).status_code, 302)
                self.client.force_login(self.staff)
                self.assertContains(self.client.get("/fields/map/"), url)
                with closing(self.client.get(url)) as response:
                    self.assertEqual(response["Content-Type"], "application/geo+json")
                    self.assertIn("no-store", response["Cache-Control"])
                    self.assertEqual(b"".join(response.streaming_content), content)
                self.assertEqual(self.client.get("/fields/map/layers/missing/").status_code, 404)
