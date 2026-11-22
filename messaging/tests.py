from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from .models import Advisory, AdvisoryDispatch, AgronomicCase, Conversation, Field, Farmer, Message, SpatialLayer
from .services import handle_inbound_sms
from .tasks import dispatch_scheduled_advisories

User = get_user_model()

class MessagingFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="farmer1", password="test-pass-123")
        self.farmer = Farmer.objects.create(user=self.user, name="Test Farmer", phone="+639171234567", phone_verified=True, sms_opt_in=True)
        self.field = Field.objects.create(farmer=self.farmer, code="F03", name="North plot")
        self.officer = User.objects.create_user(username="officer1", password="test-pass-123", is_staff=True)

    def test_root_url_has_navigation_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Farmer messaging and field advice")
        self.assertContains(response, "/officer/")

    def test_api_index_is_public_but_farmer_data_requires_authentication(self):
        response = self.client.get("/api/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("fields", response.data)
        self.assertIn("authentication", response.data)
        protected = self.client.get("/api/fields/")
        self.assertEqual(protected.status_code, 401)

    def test_sms_advisory_uses_only_approved_current_field_advice(self):
        Advisory.objects.create(field=self.field, title="Irrigate today", body="Apply a light irrigation.", approved=False, published_at=timezone.now())
        published = timezone.now() - timedelta(days=1)
        Advisory.objects.create(field=self.field, title="Water check", body="Check soil moisture first.", approved=True, published_at=published)
        _, reply = handle_inbound_sms(self.farmer.phone, "IRRIGATION F03", "SM-test-1")
        self.assertIn("Water check", reply)
        self.assertIn("Check soil moisture first", reply)
        self.assertNotIn("Irrigate today", reply)
        conversation = Conversation.objects.get(farmer=self.farmer)
        self.assertEqual(conversation.field, self.field)
        self.assertEqual(conversation.status, "answered")
        self.assertEqual(conversation.messages.count(), 2)

    def test_sms_followup_reuses_conversation_and_duplicate_webhook_is_idempotent(self):
        first, _ = handle_inbound_sms(self.farmer.phone, "The leaves are yellow", "SM-test-2")
        second, _ = handle_inbound_sms(self.farmer.phone, "Can you call me?", "SM-test-3")
        duplicate, _ = handle_inbound_sms(self.farmer.phone, "The leaves are yellow", "SM-test-2")
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.pk, duplicate.pk)
        self.assertEqual(Message.objects.filter(conversation=first, direction="inbound").count(), 2)
        self.assertEqual(first.status, "awaiting_officer")

    def test_unverified_number_cannot_open_a_farmer_conversation(self):
        self.farmer.phone_verified = False
        self.farmer.save(update_fields=["phone_verified"])
        conversation, reply = handle_inbound_sms(self.farmer.phone, "IRRIGATION F03", "SM-test-4")
        self.assertIsNone(conversation)
        self.assertIn("not registered", reply)
        self.assertFalse(Conversation.objects.exists())
        inbound = Message.objects.get(provider_id="SM-test-4")
        self.assertEqual(inbound.processing_status, "processed")
        self.assertIsNone(inbound.conversation)

    def test_sms_phone_normalization_and_open_issue_create_review_case(self):
        self.farmer.phone = "+639171234567"
        self.farmer.save(update_fields=["phone"])
        conversation, reply = handle_inbound_sms("09171234567", "The leaves on F03 are turning yellow", "SM-test-5")
        self.assertEqual(conversation.field, self.field)
        self.assertIn("sent to your extension officer", reply)
        case = AgronomicCase.objects.get(conversation=conversation)
        self.assertEqual(case.status, "awaiting_review")
        self.assertEqual(conversation.messages.filter(direction="inbound").count(), 1)

    def test_stop_and_start_update_sms_opt_in(self):
        handle_inbound_sms(self.farmer.phone, "STOP", "SM-test-6")
        self.farmer.refresh_from_db()
        self.assertFalse(self.farmer.sms_opt_in)
        self.assertIsNotNone(self.farmer.sms_opt_out_at)
        handle_inbound_sms(self.farmer.phone, "START", "SM-test-7")
        self.farmer.refresh_from_db()
        self.assertTrue(self.farmer.sms_opt_in)
        self.assertEqual(self.farmer.sms_opt_in_source, "sms")

    def test_app_issue_creates_case_and_officer_reply_answers_it(self):
        farmer_client = APIClient()
        farmer_client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.user).key}")
        issue = farmer_client.post("/api/messages/", {"field": self.field.pk, "body": "The leaves on F03 are turning yellow"}, format="json")
        self.assertEqual(issue.status_code, 201)
        conversation_id = issue.data["id"]
        self.assertEqual(issue.data["status"], "awaiting_officer")
        self.assertEqual(issue.data["case_status"], "awaiting_review")

        officer_client = APIClient()
        officer_client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.officer).key}")
        reply = officer_client.post(f"/api/conversations/{conversation_id}/reply/", {"body": "Please inspect soil moisture and send a follow-up photo."}, format="json")
        self.assertEqual(reply.status_code, 200)
        conversation = Conversation.objects.get(pk=conversation_id)
        self.assertEqual(conversation.status, "answered")
        self.assertEqual(conversation.case.status, "answered")

    def test_spatial_layers_are_visible_to_officers_but_not_restricted_to_farmers(self):
        layer = SpatialLayer.objects.create(
            field=self.field,
            name="Latest NDVI",
            service_url="https://maps.example.test/geoserver/wms",
            layer_name="onion:f03_ndvi",
            restricted=True,
        )
        farmer_client = APIClient()
        farmer_client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.user).key}")
        self.assertEqual(farmer_client.get(f"/api/spatial-layers/?field={self.field.pk}").data, [])

        officer_client = APIClient()
        officer_client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.officer).key}")
        response = officer_client.get(f"/api/spatial-layers/?field={self.field.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["id"], layer.pk)

    def test_scheduled_advisory_dispatch_is_opt_in_and_idempotent(self):
        advisory = Advisory.objects.create(
            field=self.field,
            topic="irrigation",
            title="Scheduled irrigation check",
            body="Check soil moisture before irrigating.",
            approved=True,
            published_at=timezone.now() - timedelta(minutes=5),
            scheduled_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertEqual(dispatch_scheduled_advisories(), 1)
        dispatch = AdvisoryDispatch.objects.get(advisory=advisory, farmer=self.farmer)
        self.assertEqual(dispatch.status, "failed")
        self.assertEqual(dispatch.message.intent, "scheduled_advisory")
        self.assertEqual(dispatch_scheduled_advisories(), 0)

        self.farmer.sms_opt_in = False
        self.farmer.save(update_fields=["sms_opt_in"])
        second = Advisory.objects.create(
            field=self.field,
            topic="irrigation",
            title="Opt-in required",
            body="This message should be skipped.",
            approved=True,
            published_at=timezone.now() - timedelta(minutes=5),
            scheduled_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertEqual(dispatch_scheduled_advisories(), 1)
        self.assertEqual(AdvisoryDispatch.objects.get(advisory=second).status, "skipped")

    def test_farmer_sees_only_own_conversations_and_officer_can_reply(self):
        other_user = User.objects.create_user(username="farmer2", password="test-pass-123")
        other = Farmer.objects.create(user=other_user, name="Other Farmer", phone="+639171234568", phone_verified=True)
        own_conversation = Conversation.objects.create(farmer=self.farmer, channel="app", status="awaiting_officer")
        other_conversation = Conversation.objects.create(farmer=other, channel="app", status="awaiting_officer")
        Message.objects.create(conversation=own_conversation, direction="inbound", body="My crop is yellow", channel="app")
        Message.objects.create(conversation=other_conversation, direction="inbound", body="Other crop report", channel="app")

        farmer_client = APIClient()
        farmer_client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.user).key}")
        response = farmer_client.get("/api/conversations/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({item["id"] for item in response.data}, {own_conversation.pk})
        forbidden_reply = farmer_client.post(f"/api/conversations/{other_conversation.pk}/reply/", {"body": "Private"}, format="json")
        self.assertEqual(forbidden_reply.status_code, 404)

        officer_client = APIClient()
        officer_client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.officer).key}")
        reply = officer_client.post(f"/api/conversations/{own_conversation.pk}/reply/", {"body": "Please inspect the soil."}, format="json")
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(own_conversation.messages.filter(direction="outbound", body="Please inspect the soil.").count(), 1)
        own_conversation.refresh_from_db()
        self.assertEqual(own_conversation.status, "answered")
