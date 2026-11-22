import os
from datetime import timedelta

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from .models import Advisory, AdvisoryDispatch, Conversation, Field, Farmer, Message, SpatialLayer
from .serializers import AdvisorySerializer, ConversationSerializer, FieldSerializer, SpatialLayerSerializer
from .services import process_inbound_message, queue_sms, record_inbound_sms
from .tasks import process_inbound

def farmer_for(user): return Farmer.objects.filter(user=user).first()

class FieldViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FieldSerializer
    def get_queryset(self):
        if self.request.user.is_staff:
            return Field.objects.select_related("farmer").all()
        return Field.objects.filter(farmer=farmer_for(self.request.user))

class AdvisoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AdvisorySerializer
    def get_queryset(self):
        queryset = Advisory.objects.filter(approved=True, published_at__lte=timezone.now()).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=timezone.now()))
        queryset = queryset if self.request.user.is_staff else queryset.filter(field__farmer=farmer_for(self.request.user))
        field_id = self.request.query_params.get("field")
        return queryset.filter(field_id=field_id) if field_id else queryset


class SpatialLayerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SpatialLayerSerializer

    def get_queryset(self):
        queryset = SpatialLayer.objects.select_related("field", "model_run")
        if not self.request.user.is_staff:
            queryset = queryset.filter(field__farmer=farmer_for(self.request.user), restricted=False)
        field_id = self.request.query_params.get("field")
        return queryset.filter(field_id=field_id) if field_id else queryset

class ConversationViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationSerializer
    http_method_names = ["get", "post", "head", "options"]
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
        msg = Message.objects.create(
            conversation=conversation,
            direction="outbound",
            sender=request.user,
            body=body,
            channel=channel,
            delivery_status=state,
            processing_status="processed",
            recipient_phone=conversation.farmer.phone if channel == "sms" else "",
            processed_at=timezone.now(),
            last_error="SMS opt-in is not active." if channel == "sms" and not allowed else "",
        )
        if channel == "sms" and allowed: queue_sms(msg)
        conversation.status = "answered"; conversation.save(update_fields=["status", "updated_at"])
        if hasattr(conversation, "case"):
            conversation.case.status = "answered"
            conversation.case.answered_at = timezone.now()
            conversation.case.save(update_fields=["status", "answered_at"])
        return Response(self.get_serializer(conversation).data)

def create_app_message(request):
    farmer = farmer_for(request.user)
    if not farmer: return Response({"detail": "Farmer account is not linked."}, status=403)
    body = str(request.data.get("body", "")).strip()
    if not body: return Response({"body": "This field is required."}, status=400)
    field = get_object_or_404(Field, pk=request.data.get("field"), farmer=farmer) if request.data.get("field") else None
    active = farmer.conversations.filter(status__in=["open", "awaiting_officer", "answered"], updated_at__gte=timezone.now()-timedelta(days=30), channel="app")
    if field: active = active.filter(field=field)
    conv = active.order_by("-updated_at").first() or Conversation.objects.create(farmer=farmer, field=field, channel="app", status="open")
    conv.channel = "app"
    if field: conv.field = field
    conv.status = "awaiting_officer"
    conv.subject = conv.subject or body[:180]
    conv.save(update_fields=["channel", "field", "status", "subject", "updated_at"])
    Message.objects.create(
        conversation=conv,
        direction="inbound",
        body=body,
        channel="app",
        processing_status="processed",
        intent="field_issue",
        photo=request.FILES.get("photo"),
        received_at=timezone.now(),
        processed_at=timezone.now(),
    )
    from .models import AgronomicCase
    AgronomicCase.objects.get_or_create(conversation=conv, defaults={"intent": "field_issue", "status": "awaiting_review"})
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
    raw_payload = {key: request.data.get(key) for key in request.data.keys()}
    message = record_inbound_sms(phone, body, request.data.get("MessageSid", ""), raw_payload)
    if message.processing_status != "processed":
        if settings.CELERY_BROKER_URL:
            transaction.on_commit(lambda: process_inbound.delay(message.pk))
        else:
            transaction.on_commit(lambda: process_inbound_message(message.pk))
    return HttpResponse('<?xml version="1.0" encoding="UTF-8"?><Response></Response>', content_type="application/xml")

@api_view(["POST"])
@permission_classes([AllowAny])
def sms_status(request):
    states = {"queued": "queued", "sending": "queued", "sent": "sent", "delivered": "delivered", "failed": "failed", "undelivered": "failed"}
    sid = request.data.get("MessageSid")
    if sid:
        status = states.get(request.data.get("MessageStatus"), "queued")
        message = Message.objects.filter(provider_id=sid, direction="outbound").first()
        if message:
            message.delivery_status = status
            if status == "delivered": message.delivered_at = timezone.now()
            message.save(update_fields=["delivery_status", "delivered_at"] if status == "delivered" else ["delivery_status"])
            AdvisoryDispatch.objects.filter(message=message).update(status=status)
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
        "spatial_layers": reverse("spatial-layer-list", request=request),
        "send_message": reverse("app-message", request=request),
    })

class FarmerTokenAuth(ObtainAuthToken):
    """Return an API token for the Expo client after Django user login."""
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code != 200: return response
        token = Token.objects.get(key=response.data["token"])
        return Response({"token": token.key, "is_officer": token.user.is_staff})
