from celery import shared_task
from .models import Message
from .services import send_sms

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def deliver_sms(self, message_id):
    try:
        message = Message.objects.select_related("conversation__farmer").get(pk=message_id)
        return send_sms(message).delivery_status
    except Message.DoesNotExist:
        return "missing"
    except Exception as exc:
        raise self.retry(exc=exc)
