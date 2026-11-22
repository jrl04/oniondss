from django.conf import settings
from django.db import models


class Farmer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="farmer_profile")
    name = models.CharField(max_length=160)
    phone = models.CharField(max_length=24, unique=True)
    language = models.CharField(max_length=12, default="en")
    sms_opt_in = models.BooleanField(default=False)
    sms_opt_in_at = models.DateTimeField(null=True, blank=True)
    sms_opt_out_at = models.DateTimeField(null=True, blank=True)
    sms_opt_in_source = models.CharField(max_length=40, blank=True)
    consent_version = models.CharField(max_length=40, blank=True)
    phone_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.name


class Field(models.Model):
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name="fields")
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=120, blank=True)
    crop = models.CharField(max_length=80, default="onion")
    season = models.CharField(max_length=40, blank=True)
    area_ha = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    boundary = models.JSONField(null=True, blank=True)
    geometry_revision = models.PositiveIntegerField(default=1)
    geometry_source = models.CharField(max_length=80, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["farmer", "code"], name="unique_farmer_field_code")]

    def __str__(self): return f"{self.code} — {self.farmer.name}"


class ModelRun(models.Model):
    RUN_TYPES = [("gee_ndvi", "GEE NDVI"), ("aquacrop", "AquaCrop"), ("calibration", "Canopy calibration")]
    STATUSES = [("queued", "Queued"), ("running", "Running"), ("succeeded", "Succeeded"), ("failed", "Failed")]

    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name="model_runs")
    run_type = models.CharField(max_length=20, choices=RUN_TYPES)
    season = models.CharField(max_length=40, blank=True)
    source_version = models.CharField(max_length=120, blank=True)
    parameters = models.JSONField(default=dict, blank=True)
    artifact_uri = models.CharField(max_length=500, blank=True)
    checksum = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=12, choices=STATUSES, default="queued")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class CropObservation(models.Model):
    SOURCES = [
        ("gee_ndvi", "GEE NDVI"),
        ("field_canopy", "Observed field canopy"),
        ("aquacrop_simulated", "AquaCrop simulated canopy"),
        ("calibrated_canopy", "Calibrated canopy"),
    ]

    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name="crop_observations")
    model_run = models.ForeignKey(ModelRun, null=True, blank=True, on_delete=models.SET_NULL, related_name="observations")
    observed_on = models.DateField()
    source = models.CharField(max_length=24, choices=SOURCES)
    value = models.FloatField()
    quality_flags = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["observed_on", "source"]
        indexes = [models.Index(fields=["field", "observed_on", "source"], name="cropobs_field_date_source_idx")]


class SpatialLayer(models.Model):
    SERVICE_TYPES = [("wms", "WMS"), ("wmts", "WMTS"), ("vector", "Vector")]

    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name="spatial_layers")
    model_run = models.ForeignKey(ModelRun, null=True, blank=True, on_delete=models.SET_NULL, related_name="spatial_layers")
    name = models.CharField(max_length=160)
    service_type = models.CharField(max_length=12, choices=SERVICE_TYPES, default="wms")
    service_url = models.URLField(max_length=500)
    layer_name = models.CharField(max_length=180)
    style_name = models.CharField(max_length=120, blank=True)
    cache_version = models.CharField(max_length=80, blank=True)
    restricted = models.BooleanField(default=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name", "-published_at"]


class Advisory(models.Model):
    TOPICS = [("general", "General"), ("irrigation", "Irrigation"), ("pest", "Pest"), ("disease", "Disease")]

    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name="advisories")
    topic = models.CharField(max_length=32, choices=TOPICS, default="general")
    language = models.CharField(max_length=12, default="en")
    title = models.CharField(max_length=180)
    body = models.TextField()
    approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_advisories")
    approved_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta: ordering = ["-published_at", "-created_at"]


class Conversation(models.Model):
    CHANNELS = [("app", "Mobile app"), ("sms", "SMS")]
    STATUSES = [("open", "Open"), ("awaiting_officer", "Awaiting officer"), ("answered", "Answered"), ("closed", "Closed")]
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name="conversations")
    field = models.ForeignKey(Field, null=True, blank=True, on_delete=models.SET_NULL, related_name="conversations")
    channel = models.CharField(max_length=8, choices=CHANNELS, default="app")
    language = models.CharField(max_length=12, default="en")
    status = models.CharField(max_length=20, choices=STATUSES, default="open")
    subject = models.CharField(max_length=180, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_conversations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class AgronomicCase(models.Model):
    STATUSES = [("open", "Open"), ("awaiting_review", "Awaiting review"), ("assigned", "Assigned"), ("in_progress", "In progress"), ("answered", "Answered"), ("closed", "Closed")]
    PRIORITIES = [("normal", "Normal"), ("high", "High"), ("urgent", "Urgent")]

    conversation = models.OneToOneField(Conversation, on_delete=models.CASCADE, related_name="case")
    intent = models.CharField(max_length=80, default="field_issue")
    status = models.CharField(max_length=20, choices=STATUSES, default="awaiting_review")
    priority = models.CharField(max_length=10, choices=PRIORITIES, default="normal")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="agronomic_cases")
    opened_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)


class Message(models.Model):
    DIRECTIONS = [("inbound", "Inbound"), ("outbound", "Outbound")]
    DELIVERY = [("received", "Received"), ("queued", "Queued"), ("sent", "Sent"), ("delivered", "Delivered"), ("failed", "Failed")]
    PROCESSING = [("received", "Received"), ("processing", "Processing"), ("processed", "Processed"), ("failed", "Failed")]
    conversation = models.ForeignKey(Conversation, null=True, blank=True, on_delete=models.CASCADE, related_name="messages")
    direction = models.CharField(max_length=8, choices=DIRECTIONS)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    body = models.TextField()
    photo = models.ImageField(upload_to="message-photos/%Y/%m/", null=True, blank=True)
    channel = models.CharField(max_length=8, choices=Conversation.CHANNELS)
    delivery_status = models.CharField(max_length=12, choices=DELIVERY, default="received")
    processing_status = models.CharField(max_length=12, choices=PROCESSING, default="received")
    intent = models.CharField(max_length=80, blank=True)
    classification_confidence = models.FloatField(null=True, blank=True)
    provider_id = models.CharField(max_length=80, blank=True, db_index=True)
    phone_number = models.CharField(max_length=24, blank=True)
    recipient_phone = models.CharField(max_length=24, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    last_error = models.TextField(blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [models.UniqueConstraint(fields=["provider_id"], condition=~models.Q(provider_id=""), name="unique_nonempty_message_provider_id")]


class AdvisoryDispatch(models.Model):
    STATUSES = [("queued", "Queued"), ("sent", "Sent"), ("delivered", "Delivered"), ("failed", "Failed"), ("skipped", "Skipped")]

    advisory = models.ForeignKey(Advisory, on_delete=models.CASCADE, related_name="dispatches")
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name="advisory_dispatches")
    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name="advisory_dispatches")
    channel = models.CharField(max_length=8, choices=Conversation.CHANNELS, default="sms")
    status = models.CharField(max_length=12, choices=STATUSES, default="queued")
    message = models.OneToOneField(Message, null=True, blank=True, on_delete=models.SET_NULL, related_name="advisory_dispatch")
    scheduled_for = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["advisory", "farmer", "channel"], name="unique_advisory_farmer_channel")]
