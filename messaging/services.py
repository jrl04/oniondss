import logging
import re
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Advisory, AdvisoryDispatch, AgronomicCase, Conversation, Farmer, Message

logger = logging.getLogger(__name__)


def normalize_phone(phone):
    value = re.sub(r"[^0-9+]", "", str(phone or "").strip())
    if value.startswith("00"):
        value = "+" + value[2:]
    if value.startswith("63"):
        value = "+" + value
    elif value.startswith("09") and len(value) == 11:
        value = "+63" + value[1:]
    return value


def farmer_for_phone(phone):
    normalized = normalize_phone(phone)
    return Farmer.objects.filter(Q(phone=normalized) | Q(phone=phone)).first()


def extract_field(farmer, body):
    match = re.search(r"\bF\s*-?\s*\d+\b", body or "", re.IGNORECASE)
    if not match:
        return None
    code = re.sub(r"\s+", "", match.group(0)).replace("-", "")
    return farmer.fields.filter(code__iexact=code).first()


def latest_advisory(field, topic="general", language="en"):
    now = timezone.now()
    active = Advisory.objects.filter(
        field=field,
        approved=True,
        published_at__isnull=False,
        published_at__lte=now,
    ).filter(Q(topic=topic) | Q(topic="general")).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
    localized = active.filter(language=language).first()
    return localized or active.filter(language="en").first() or active.first()


def _recent_conversation(farmer, field, channel):
    active = farmer.conversations.filter(
        status__in=["open", "awaiting_officer", "answered"],
        updated_at__gte=timezone.now() - timedelta(days=30),
        channel=channel,
    )
    if field:
        active = active.filter(field=field)
    else:
        active = active.filter(field__isnull=True)
    return active.order_by("-updated_at").first()


def _conversation_for(farmer, field, channel):
    conversation = _recent_conversation(farmer, field, channel)
    if conversation:
        return conversation
    return Conversation.objects.create(
        farmer=farmer,
        field=field,
        channel=channel,
        language=farmer.language,
    )


@transaction.atomic
def record_inbound_sms(phone, body, provider_id="", raw_payload=None):
    normalized = normalize_phone(phone)
    if provider_id:
        duplicate = Message.objects.filter(provider_id=provider_id, direction="inbound").first()
        if duplicate:
            return duplicate
    return Message.objects.create(
        direction="inbound",
        body=str(body or "").strip(),
        channel="sms",
        provider_id=provider_id or "",
        phone_number=normalized,
        raw_payload=raw_payload or {},
        delivery_status="received",
        processing_status="received",
        received_at=timezone.now(),
    )


def _create_outbound(conversation, body, phone, delivery_channel="sms"):
    message = Message.objects.create(
        conversation=conversation,
        direction="outbound",
        body=body,
        channel=delivery_channel,
        delivery_status="queued" if delivery_channel == "sms" else "delivered",
        processing_status="processed",
        recipient_phone=normalize_phone(phone),
        processed_at=timezone.now(),
    )
    if delivery_channel == "sms":
        transaction.on_commit(lambda message_id=message.pk: queue_sms(Message.objects.get(pk=message_id)))
    return message


def _mark_case_for_review(conversation, intent="field_issue"):
    case, _ = AgronomicCase.objects.get_or_create(
        conversation=conversation,
        defaults={"intent": intent, "status": "awaiting_review"},
    )
    case.intent = intent
    case.status = "awaiting_review"
    case.save(update_fields=["intent", "status"])
    conversation.status = "awaiting_officer"
    conversation.save(update_fields=["status", "updated_at"])
    return case


def process_inbound_message(message_id):
    with transaction.atomic():
        message = Message.objects.select_for_update().select_related("conversation").get(pk=message_id)
        if message.processing_status in {"processing", "processed"}:
            return message.conversation, ""
        message.processing_status = "processing"
        message.save(update_fields=["processing_status"])
    farmer = farmer_for_phone(message.phone_number)
    text = message.body.strip()
    upper = text.upper()
    reply = ""
    conversation = None

    try:
        if not farmer or not farmer.phone_verified:
            reply = "Your number is not registered. Please contact your extension officer to link your account."
        else:
            field = extract_field(farmer, text)
            conversation = _conversation_for(farmer, field, "sms")
            message.conversation = conversation
            message.intent = "field_issue"
            message.save(update_fields=["conversation", "intent", "processing_status"])

            if upper == "STOP":
                farmer.sms_opt_in = False
                farmer.sms_opt_out_at = timezone.now()
                farmer.save(update_fields=["sms_opt_in", "sms_opt_out_at"])
                reply = "SMS messages stopped. Text START to opt in again."
            elif upper == "START":
                farmer.sms_opt_in = True
                farmer.sms_opt_in_at = timezone.now()
                farmer.sms_opt_in_source = "sms"
                farmer.save(update_fields=["sms_opt_in", "sms_opt_in_at", "sms_opt_in_source"])
                reply = "You are opted in to DSS SMS updates. Text HELP for instructions."
            elif upper == "HELP":
                reply = "Send IRRIGATION <field code> for approved advice, or describe an issue for your extension officer. Text STOP to opt out."
            elif re.match(r"^IRRIGATION(?:\s+\S+)?$", upper):
                message.intent = "advisory_request"
                message.save(update_fields=["intent"])
                if not field:
                    requested_code = text.split(maxsplit=1)[1].strip() if len(text.split(maxsplit=1)) == 2 else ""
                    reply = f"Field {requested_code} is not linked to your account. Check the code or contact your extension officer."
                else:
                    advisory = latest_advisory(field, topic="irrigation", language=farmer.language)
                    if advisory:
                        reply = f"{advisory.title} ({advisory.published_at:%d %b %Y}): {advisory.body}"
                        conversation.status = "answered"
                        conversation.save(update_fields=["status", "updated_at"])
                    else:
                        _mark_case_for_review(conversation, "irrigation_advisory_request")
                        reply = f"No approved irrigation advisory is available for {field.code}. Your request has been forwarded to an extension officer."
            else:
                _mark_case_for_review(conversation)
                reply = "Thanks, your message was received and sent to your extension officer. We will reply here."
                conversation.subject = conversation.subject or text[:180]
                conversation.save(update_fields=["subject", "updated_at"])

        if reply:
            _create_outbound(conversation, reply, message.phone_number)
        message.processing_status = "processed"
        message.processed_at = timezone.now()
        message.save(update_fields=["processing_status", "processed_at"])
        return conversation, reply
    except Exception as exc:
        Message.objects.filter(pk=message_id).update(processing_status="failed", last_error=str(exc))
        logger.exception("Inbound message processing failed for message=%s", message_id)
        raise


def handle_inbound_sms(phone, body, provider_id="", raw_payload=None):
    message = record_inbound_sms(phone, body, provider_id, raw_payload)
    if message.processing_status == "processed":
        return message.conversation, ""
    return process_inbound_message(message.pk)


def send_sms(message):
    def update_dispatch():
        AdvisoryDispatch.objects.filter(message=message).update(status=message.delivery_status)

    if message.delivery_status in {"sent", "delivered"} and message.provider_id:
        return message
    recipient = message.recipient_phone or (message.conversation.farmer.phone if message.conversation_id else "")
    if not recipient:
        message.delivery_status = "failed"
        message.last_error = "No SMS recipient is available."
        message.save(update_fields=["delivery_status", "last_error"])
        update_dispatch()
        return message
    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_NUMBER):
        message.delivery_status = "failed"
        message.last_error = "SMS provider credentials are not configured."
        message.save(update_fields=["delivery_status", "last_error"])
        update_dispatch()
        return message
    try:
        from twilio.rest import Client

        result = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN).messages.create(
            to=recipient,
            from_=settings.TWILIO_FROM_NUMBER,
            body=message.body,
            status_callback=f"{settings.PUBLIC_BASE_URL}/api/webhooks/sms/status/",
        )
        message.provider_id = result.sid
        message.delivery_status = "sent"
        message.sent_at = timezone.now()
        message.last_error = ""
        message.save(update_fields=["provider_id", "delivery_status", "sent_at", "last_error"])
        update_dispatch()
    except Exception as exc:
        logger.exception("SMS delivery failed for message=%s", message.pk)
        message.delivery_status = "failed"
        message.last_error = str(exc)
        message.save(update_fields=["delivery_status", "last_error"])
        update_dispatch()
    return message


def queue_sms(message):
    message.delivery_status = "queued"
    message.save(update_fields=["delivery_status"])
    if settings.CELERY_BROKER_URL:
        from .tasks import deliver_sms

        try:
            deliver_sms.delay(message.pk)
        except Exception as exc:
            logger.exception("Could not queue SMS for message=%s", message.pk)
            message.delivery_status = "failed"
            message.last_error = str(exc)
            message.save(update_fields=["delivery_status", "last_error"])
        return message
    return send_sms(message)
