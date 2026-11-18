import os
from datetime import timedelta
from xml.sax.saxutils import escape
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from .models import Advisory, Conversation, Field, Farmer, Message
from .serializers import AdvisorySerializer, ConversationSerializer, FieldSerializer
from .services import handle_inbound_sms, queue_sms

def farmer_for(user): return Farmer.objects.filter(user=user).first()

class FieldViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FieldSerializer
    def get_queryset(self): return Field.objects.filter(farmer=farmer_for(self.request.user))

class AdvisoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AdvisorySerializer
    def get_queryset(self): return Advisory.objects.filter(field__farmer=farmer_for(self.request.user), approved=True, published_at__lte=timezone.now())

class ConversationViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationSerializer
    def get_queryset(self):
        qs = Conversation.objects.select_related("farmer", "field").prefetch_related("messages")
        return qs if self.request.user.is_staff else qs.filter(farmer=farmer_for(self.request.user))
    def create(self, request, *args, **kwargs):
        return create_app_message(request)
    @action(detail=True, methods=["post"])
    def reply(self, request, pk=None):
        conversation = self.get_object()
        if not request.user.is_staff: return Response({"detail": "Officer access required."}, status=403)
        body = str(request.data.get("body", "")).strip()
        if not body: return Response({"body": "This field is required."}, status=400)
        channel = conversation.messages.filter(direction="inbound").order_by("-created_at").values_list("channel", flat=True).first() or conversation.channel
        allowed = channel != "sms" or conversation.farmer.sms_opt_in
        state = "queued" if channel == "sms" and allowed else ("failed" if channel == "sms" else "delivered")
        msg = Message.objects.create(conversation=conversation, direction="outbound", sender=request.user, body=body, channel=channel, delivery_status=state)
        if channel == "sms" and conversation.farmer.sms_opt_in: queue_sms(msg)
        conversation.status = "answered"; conversation.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(conversation).data)

def create_app_message(request):
    farmer = farmer_for(request.user)
    if not farmer: return Response({"detail": "Farmer account is not linked."}, status=403)
    body = str(request.data.get("body", "")).strip()
    if not body: return Response({"body": "This field is required."}, status=400)
    field = get_object_or_404(Field, pk=request.data.get("field"), farmer=farmer) if request.data.get("field") else None
    active = farmer.conversations.filter(status__in=["open", "awaiting_officer", "answered"], updated_at__gte=timezone.now()-timedelta(days=30))
    if field: active = active.filter(field=field)
    conv = active.order_by("-updated_at").first() or Conversation.objects.create(farmer=farmer, field=field, channel="app", status="open")
    conv.channel = "app"
    if field: conv.field = field
    conv.status = "awaiting_officer"
    conv.subject = conv.subject or body[:180]
    conv.save(update_fields=["channel", "field", "status", "subject", "updated_at"])
    Message.objects.create(conversation=conv, direction="inbound", body=body, channel="app", photo=request.FILES.get("photo"))
    conv.save(update_fields=["updated_at"])
    return Response(ConversationSerializer(conv, context={"request": request}).data, status=201)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def app_message(request): return create_app_message(request)

@api_view(["POST"])
@permission_classes([AllowAny])
def sms_inbound(request):
    # Twilio signs callbacks; enforce signatures outside debug mode by default.
    if not settings.DEBUG and os.getenv("SMS_VALIDATE_SIGNATURE", "1") == "1":
        from twilio.request_validator import RequestValidator
        signature = request.headers.get("X-Twilio-Signature", "")
        validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
        if not settings.TWILIO_AUTH_TOKEN or not validator.validate(request.build_absolute_uri(), request.POST, signature):
            return HttpResponse("Invalid signature", status=403)
    phone, body = request.data.get("From", ""), request.data.get("Body", "")
    if not phone or not body: return HttpResponse("Missing From or Body", status=400)
    _, reply = handle_inbound_sms(phone, body, request.data.get("MessageSid", ""))
    callback = escape(request.build_absolute_uri("/api/webhooks/sms/status/"), {'"': '&quot;'})
    return HttpResponse(f'<?xml version="1.0" encoding="UTF-8"?><Response><Message statusCallback="{callback}">{escape(reply)}</Message></Response>', content_type="application/xml")

@api_view(["POST"])
@permission_classes([AllowAny])
def sms_status(request):
    states = {"queued": "queued", "sending": "queued", "sent": "sent", "delivered": "delivered", "failed": "failed", "undelivered": "failed"}
    sid = request.data.get("MessageSid")
    if sid:
        changed = Message.objects.filter(provider_id=sid).update(delivery_status=states.get(request.data.get("MessageStatus"), "queued"))
        # TwiML replies do not expose their generated SID until the status callback arrives.
        if not changed and request.data.get("To"):
            pending = Message.objects.filter(provider_id="", direction="outbound", channel="sms", delivery_status="queued", conversation__farmer__phone=request.data["To"]).order_by("-created_at").first()
            if pending:
                pending.provider_id = sid
                pending.delivery_status = states.get(request.data.get("MessageStatus"), "queued")
                pending.save(update_fields=["provider_id", "delivery_status"])
    return Response({"ok": True})

@staff_member_required
def officer_inbox(request):
    return render(request, "messaging/officer.html")

def home(request):
    return render(request, "messaging/home.html")

@api_view(["GET"])
@permission_classes([AllowAny])
def api_root(request):
    return Response({
        "authentication": reverse("api-token-auth", request=request),
        "fields": reverse("field-list", request=request),
        "advisories": reverse("advisory-list", request=request),
        "conversations": reverse("conversation-list", request=request),
        "send_message": reverse("app-message", request=request),
    })

class FarmerTokenAuth(ObtainAuthToken):
    """Return an API token for the Expo client after Django user login."""
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code != 200: return response
        token = Token.objects.get(key=response.data["token"])
        return Response({"token": token.key, "is_officer": token.user.is_staff})
