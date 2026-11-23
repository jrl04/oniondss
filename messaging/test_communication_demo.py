from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .management.commands.seed_communication_demo import PASSWORD, PHONE, TITLE, USERNAME
from .models import Advisory, Field, Message


class CommunicationDemoTests(TestCase):
    @override_settings(DEBUG=True, CELERY_BROKER_URL="")
    @patch("messaging.services.queue_sms")
    def test_admin_publication_reaches_mobile_and_simulated_sms(self, queue_sms):
        call_command("seed_communication_demo")
        field = Field.objects.get(farmer__user__username=USERNAME, code="F03")
        Advisory.objects.filter(field=field).update(published_at=timezone.now() - timezone.timedelta(hours=1))
        admin = get_user_model().objects.create_superuser("demo-officer", password="test-password")
        self.client.force_login(admin)

        mobile = APIClient()
        login = mobile.post("/api/auth/token/", {"username": USERNAME, "password": PASSWORD}, format="json")
        self.assertEqual(login.status_code, 200)
        mobile.credentials(HTTP_AUTHORIZATION=f"Token {login.data['token']}")
        self.assertEqual([row["title"] for row in mobile.get("/api/advisories/").data], [TITLE])

        title = "[Demo] Review the low end of F03"
        published = timezone.localtime() - timezone.timedelta(minutes=1)
        result = self.client.post("/admin/messaging/advisory/add/", {
            "field": field.pk, "topic": "irrigation", "language": "en", "title": title,
            "body": "Sample update published through Django admin.",
            "approved": "on",
            "published_at_0": published.date().isoformat(),
            "published_at_1": published.strftime("%H:%M:%S"),
        })
        self.assertEqual(result.status_code, 302)
        self.assertIn(title, [row["title"] for row in mobile.get("/api/advisories/").data])

        with self.captureOnCommitCallbacks(execute=True):
            inbound = APIClient().post("/api/webhooks/sms/inbound/", {
                "From": PHONE, "Body": "IRRIGATION F03", "MessageSid": "SM-demo-f03",
            }, format="multipart")
        self.assertEqual(inbound.status_code, 200)
        self.assertIn(title, Message.objects.get(direction="outbound", recipient_phone=PHONE).body)
        queue_sms.assert_called_once()
