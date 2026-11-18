from django.conf import settings
from django.db import models

class Farmer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="farmer_profile")
    name = models.CharField(max_length=160)
    phone = models.CharField(max_length=24, unique=True)
    language = models.CharField(max_length=12, default="en")
    sms_opt_in = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.name

class Field(models.Model):
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name="fields")
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=120, blank=True)
    crop = models.CharField(max_length=80, default="onion")
    area_ha = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    boundary = models.JSONField(null=True, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["farmer", "code"], name="unique_farmer_field_code")]
    def __str__(self): return f"{self.code} — {self.farmer.name}"

class Advisory(models.Model):
    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name="advisories")
    title = models.CharField(max_length=180)
    body = models.TextField()
    approved = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["-published_at", "-created_at"]

class Conversation(models.Model):
    CHANNELS = [("app", "Mobile app"), ("sms", "SMS")]
    STATUSES = [("open", "Open"), ("awaiting_officer", "Awaiting officer"), ("answered", "Answered"), ("closed", "Closed")]
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name="conversations")
    field = models.ForeignKey(Field, null=True, blank=True, on_delete=models.SET_NULL, related_name="conversations")
    channel = models.CharField(max_length=8, choices=CHANNELS, default="app")
    status = models.CharField(max_length=20, choices=STATUSES, default="open")
    subject = models.CharField(max_length=180, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_conversations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Message(models.Model):
    DIRECTIONS = [("inbound", "Inbound"), ("outbound", "Outbound")]
    DELIVERY = [("received", "Received"), ("queued", "Queued"), ("sent", "Sent"), ("delivered", "Delivered"), ("failed", "Failed")]
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    direction = models.CharField(max_length=8, choices=DIRECTIONS)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    body = models.TextField()
    photo = models.ImageField(upload_to="message-photos/%Y/%m/", null=True, blank=True)
    channel = models.CharField(max_length=8, choices=Conversation.CHANNELS)
    delivery_status = models.CharField(max_length=12, choices=DELIVERY, default="received")
    provider_id = models.CharField(max_length=80, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["created_at"]
