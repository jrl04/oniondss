from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("messaging", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="farmer",
            name="consent_version",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="farmer",
            name="sms_opt_in_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="farmer",
            name="sms_opt_in_source",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="farmer",
            name="sms_opt_out_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="field",
            name="geometry_revision",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="field",
            name="geometry_source",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="field",
            name="season",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="field",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="advisory",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="advisory",
            name="approved_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_advisories", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="advisory",
            name="effective_to",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="advisory",
            name="scheduled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="advisory",
            name="language",
            field=models.CharField(default="en", max_length=12),
        ),
        migrations.AddField(
            model_name="advisory",
            name="topic",
            field=models.CharField(choices=[("general", "General"), ("irrigation", "Irrigation"), ("pest", "Pest"), ("disease", "Disease")], default="general", max_length=32),
        ),
        migrations.AddField(
            model_name="conversation",
            name="language",
            field=models.CharField(default="en", max_length=12),
        ),
        migrations.AlterField(
            model_name="message",
            name="conversation",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="messaging.conversation"),
        ),
        migrations.AddField(
            model_name="message",
            name="classification_confidence",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="message",
            name="delivered_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="message",
            name="intent",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="message",
            name="last_error",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="message",
            name="phone_number",
            field=models.CharField(blank=True, max_length=24),
        ),
        migrations.AddField(
            model_name="message",
            name="processed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="message",
            name="processing_status",
            field=models.CharField(choices=[("received", "Received"), ("processing", "Processing"), ("processed", "Processed"), ("failed", "Failed")], default="received", max_length=12),
        ),
        migrations.AddField(
            model_name="message",
            name="raw_payload",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="message",
            name="received_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="message",
            name="recipient_phone",
            field=models.CharField(blank=True, max_length=24),
        ),
        migrations.AddField(
            model_name="message",
            name="sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="AgronomicCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("intent", models.CharField(default="field_issue", max_length=80)),
                ("status", models.CharField(choices=[("open", "Open"), ("awaiting_review", "Awaiting review"), ("assigned", "Assigned"), ("in_progress", "In progress"), ("answered", "Answered"), ("closed", "Closed")], default="awaiting_review", max_length=20)),
                ("priority", models.CharField(choices=[("normal", "Normal"), ("high", "High"), ("urgent", "Urgent")], default="normal", max_length=10)),
                ("answered_at", models.DateTimeField(blank=True, null=True)),
                ("opened_at", models.DateTimeField(auto_now_add=True)),
                ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="agronomic_cases", to=settings.AUTH_USER_MODEL)),
                ("conversation", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="case", to="messaging.conversation")),
            ],
        ),
        migrations.CreateModel(
            name="ModelRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("run_type", models.CharField(choices=[("gee_ndvi", "GEE NDVI"), ("aquacrop", "AquaCrop"), ("calibration", "Canopy calibration")], max_length=20)),
                ("season", models.CharField(blank=True, max_length=40)),
                ("source_version", models.CharField(blank=True, max_length=120)),
                ("parameters", models.JSONField(blank=True, default=dict)),
                ("artifact_uri", models.CharField(blank=True, max_length=500)),
                ("checksum", models.CharField(blank=True, max_length=128)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("succeeded", "Succeeded"), ("failed", "Failed")], default="queued", max_length=12)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("field", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="model_runs", to="messaging.field")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="SpatialLayer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("service_type", models.CharField(choices=[("wms", "WMS"), ("wmts", "WMTS"), ("vector", "Vector")], default="wms", max_length=12)),
                ("service_url", models.URLField(max_length=500)),
                ("layer_name", models.CharField(max_length=180)),
                ("style_name", models.CharField(blank=True, max_length=120)),
                ("cache_version", models.CharField(blank=True, max_length=80)),
                ("restricted", models.BooleanField(default=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("field", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="spatial_layers", to="messaging.field")),
                ("model_run", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="spatial_layers", to="messaging.modelrun")),
            ],
            options={"ordering": ["name", "-published_at"]},
        ),
        migrations.CreateModel(
            name="CropObservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("observed_on", models.DateField()),
                ("source", models.CharField(choices=[("gee_ndvi", "GEE NDVI"), ("field_canopy", "Observed field canopy"), ("aquacrop_simulated", "AquaCrop simulated canopy"), ("calibrated_canopy", "Calibrated canopy")], max_length=24)),
                ("value", models.FloatField()),
                ("quality_flags", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("field", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="crop_observations", to="messaging.field")),
                ("model_run", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="observations", to="messaging.modelrun")),
            ],
            options={"ordering": ["observed_on", "source"]},
        ),
        migrations.AddIndex(
            model_name="cropobservation",
            index=models.Index(fields=["field", "observed_on", "source"], name="cropobs_field_date_source_idx"),
        ),
        migrations.AddConstraint(
            model_name="message",
            constraint=models.UniqueConstraint(condition=~models.Q(("provider_id", "")), fields=("provider_id",), name="unique_nonempty_message_provider_id"),
        ),
        migrations.CreateModel(
            name="AdvisoryDispatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel", models.CharField(choices=[("app", "Mobile app"), ("sms", "SMS")], default="sms", max_length=8)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("sent", "Sent"), ("delivered", "Delivered"), ("failed", "Failed"), ("skipped", "Skipped")], default="queued", max_length=12)),
                ("scheduled_for", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("advisory", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="dispatches", to="messaging.advisory")),
                ("farmer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="advisory_dispatches", to="messaging.farmer")),
                ("field", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="advisory_dispatches", to="messaging.field")),
                ("message", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="advisory_dispatch", to="messaging.message")),
            ],
        ),
        migrations.AddConstraint(
            model_name="advisorydispatch",
            constraint=models.UniqueConstraint(fields=("advisory", "farmer", "channel"), name="unique_advisory_farmer_channel"),
        ),
    ]
