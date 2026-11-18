import logging
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from .models import Advisory, Conversation, Farmer, Message
logger = logging.getLogger(__name__)

def send_sms(message):
    """Send via configured Twilio number; persist delivery state for the officer inbox."""
    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_NUMBER):
        message.delivery_status = "queued"
        message.save(update_fields=["delivery_status"])
        return message
    try:
        from twilio.rest import Client
        result = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN).messages.create(
            to=message.conversation.farmer.phone, from_=settings.TWILIO_FROM_NUMBER, body=message.body,
            status_callback=f"{settings.PUBLIC_BASE_URL}/api/webhooks/sms/status/")
        message.provider_id, message.delivery_status = result.sid, "sent"
    except Exception:
        logger.exception("SMS delivery failed for message=%s", message.pk)
        message.delivery_status = "failed"
    message.save(update_fields=["provider_id", "delivery_status"])
    return message

def queue_sms(message):
    """Use Celery when a broker is configured; keep the local prototype self-contained."""
    if settings.CELERY_BROKER_URL:
        from .tasks import deliver_sms
        message.delivery_status = "queued"
        message.save(update_fields=["delivery_status"])
        try:
            deliver_sms.delay(message.pk)
            return message
        except Exception:
            logger.exception("Could not queue SMS; attempting direct send for message=%s", message.pk)
    return send_sms(message)

def latest_advisory(field):
    return Advisory.objects.filter(field=field, approved=True, published_at__isnull=False, published_at__lte=timezone.now()).first()

def handle_inbound_sms(phone, body, provider_id=""):
    farmer = Farmer.objects.filter(phone=phone).first()
    if not farmer or not farmer.phone_verified:
        return None, "Your number is not registered. Please contact your extension officer to link your account."
    if provider_id:
        duplicate = Message.objects.filter(provider_id=provider_id).first()
        if duplicate: return duplicate.conversation, ""
    text = body.strip()
    upper = text.upper()
    field = farmer.fields.filter(code__iexact=text.split(maxsplit=1)[1].strip()).first() if upper.startswith("IRRIGATION ") else None
    active = farmer.conversations.filter(status__in=["open", "awaiting_officer", "answered"], updated_at__gte=timezone.now()-timedelta(days=30))
    if field: active = active.filter(field=field)
    elif upper.startswith("IRRIGATION "): active = active.filter(field__isnull=True)
    conversation = active.order_by("-updated_at").first() or Conversation.objects.create(farmer=farmer, field=field, channel="sms", status="open")
    conversation.channel = "sms"
    if field: conversation.field = field
    conversation.save(update_fields=["channel", "field", "updated_at"])
    Message.objects.create(conversation=conversation, direction="inbound", body=text, channel="sms", provider_id=provider_id)
    if upper == "STOP":
        farmer.sms_opt_in = False; farmer.save(update_fields=["sms_opt_in"])
        reply = "SMS messages stopped. Text START to opt in again."
    elif upper == "START":
        farmer.sms_opt_in = True; farmer.save(update_fields=["sms_opt_in"])
        reply = "You are opted in to DSS SMS updates. Text HELP for instructions."
    elif upper == "HELP":
        reply = "Send IRRIGATION <field code> for approved advice, or describe an issue for your extension officer. Text STOP to opt out."
    elif upper.startswith("IRRIGATION "):
        code = text.split(maxsplit=1)[1].strip()
        advisory = latest_advisory(field) if field else None
        if not field: reply = f"Field {code} is not linked to your account. Check the code or contact your extension officer."
        elif advisory:
            reply = f"{advisory.title} ({advisory.published_at:%d %b %Y}): {advisory.body}"
            conversation.status = "answered"; conversation.save(update_fields=["status"])
        else:
            reply = f"No current approved advisory for {field.code}. Your request has been forwarded to your extension officer."
            conversation.status = "awaiting_officer"; conversation.save(update_fields=["status"])
    else:
        conversation.status = "awaiting_officer"; conversation.subject = text[:180]
        conversation.save(update_fields=["status", "subject"])
        reply = "Thanks, your message was received and sent to your extension officer. We will reply here."
    Message.objects.create(conversation=conversation, direction="outbound", body=reply, channel="sms", delivery_status="queued")
    conversation.save(update_fields=["updated_at"])
    return conversation, reply
