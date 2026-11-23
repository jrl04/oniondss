from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from messaging.models import Advisory, Farmer, Field

USERNAME = "dss-demo-farmer"
PASSWORD = "DssDemo-F03-only"
PHONE = "+12025550143"
TITLE = "[Demo] Check soil moisture in F03"


class Command(BaseCommand):
    help = "Create a local demo farmer, field, and published sample advisory."

    @transaction.atomic
    def handle(self, **options):
        if not settings.DEBUG or connection.vendor != "sqlite":
            raise CommandError("This demo command requires DEBUG and SQLite.")
        users = get_user_model().objects
        user = users.filter(username=USERNAME).first()
        farmer = Farmer.objects.filter(phone=PHONE).first()
        if (user or farmer) and (
            not user or not farmer or farmer.user_id != user.pk
            or user.is_staff or user.is_superuser or not user.check_password(PASSWORD)
        ):
            raise CommandError("The demo username or number is already in use.")
        if user is None:
            user = users.create_user(username=USERNAME, password=PASSWORD)
            farmer = Farmer.objects.create(
                user=user, name="Elena Ramos (Demo)", phone=PHONE, phone_verified=True,
            )
        field, _ = Field.objects.get_or_create(
            farmer=farmer, code="F03",
            defaults={
                "name": "Pasuquin Demo Plot", "crop": "Multiplier onion", "area_ha": "0.45",
                "boundary": {"type": "Point", "coordinates": [120.61, 18.33]},
            },
        )
        Advisory.objects.get_or_create(
            field=field, topic="irrigation", title=TITLE,
            defaults={
                "language": "en",
                "body": "Sample advisory for testing. Check both ends of the plot and record areas where the soil is still damp.",
                "approved": True,
                "published_at": timezone.now(),
            },
        )
        self.stdout.write(f"Demo farmer: {USERNAME} | Test number: {PHONE} | Field: {field.code}")
