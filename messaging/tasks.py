from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .models import Advisory, AdvisoryDispatch, Conversation, Message
from .services import _conversation_for, normalize_phone, process_inbound_message, queue_sms, send_sms


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def process_inbound(self, message_id):
    try:
        process_inbound_message(message_id)
        return "processed"
    except Message.DoesNotExist:
        return "missing"
    except Exception as exc:
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def deliver_sms(self, message_id):
    try:
        message = Message.objects.select_related("conversation__farmer").get(pk=message_id)
        return send_sms(message).delivery_status
    except Message.DoesNotExist:
        return "missing"
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task
def dispatch_scheduled_advisories():
    now = timezone.now()
    advisories = Advisory.objects.filter(
        approved=True,
        published_at__isnull=False,
        published_at__lte=now,
        scheduled_at__isnull=False,
        scheduled_at__lte=now,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now)).select_related("field__farmer")
    created_count = 0
    for advisory in advisories:
        farmer = advisory.field.farmer
        with transaction.atomic():
            dispatch, created = AdvisoryDispatch.objects.get_or_create(
                advisory=advisory,
                farmer=farmer,
                channel="sms",
                defaults={"field": advisory.field, "scheduled_for": advisory.scheduled_at},
            )
            if not created:
                continue
            created_count += 1
            if not farmer.sms_opt_in or not farmer.phone_verified:
                dispatch.status = "skipped"
                dispatch.save(update_fields=["status"])
                continue
            conversation = _conversation_for(farmer, advisory.field, "sms")
            message = Message.objects.create(
                conversation=conversation,
                direction="outbound",
                body=f"{advisory.title} ({advisory.published_at:%d %b %Y}): {advisory.body}",
                channel="sms",
                delivery_status="queued",
                processing_status="processed",
                intent="scheduled_advisory",
                recipient_phone=normalize_phone(farmer.phone),
                processed_at=now,
            )
            dispatch.message = message
            dispatch.status = "queued"
            dispatch.save(update_fields=["message", "status"])
            transaction.on_commit(lambda message_id=message.pk: queue_sms(Message.objects.get(pk=message_id)))
    return created_count
