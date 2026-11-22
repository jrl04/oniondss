from django.contrib import admin
from .models import Advisory, AdvisoryDispatch, AgronomicCase, Conversation, CropObservation, Field, Farmer, Message, ModelRun, SpatialLayer
@admin.register(Farmer)
class FarmerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "phone_verified", "sms_opt_in", "language")
    search_fields = ("name", "phone")
@admin.register(Field)
class FieldAdmin(admin.ModelAdmin):
    list_display = ("code", "farmer", "crop", "season", "geometry_revision")
    search_fields = ("code", "name", "farmer__name")


@admin.register(Advisory)
class AdvisoryAdmin(admin.ModelAdmin):
    list_display = ("field", "topic", "language", "title", "approved", "published_at", "effective_to")
    list_filter = ("topic", "language", "approved")
    search_fields = ("field__code", "title", "body")


@admin.register(ModelRun)
class ModelRunAdmin(admin.ModelAdmin):
    list_display = ("field", "run_type", "source_version", "status", "created_at")
    list_filter = ("run_type", "status")


@admin.register(CropObservation)
class CropObservationAdmin(admin.ModelAdmin):
    list_display = ("field", "observed_on", "source", "value")
    list_filter = ("source",)


@admin.register(SpatialLayer)
class SpatialLayerAdmin(admin.ModelAdmin):
    list_display = ("field", "name", "service_type", "layer_name", "published_at")
    list_filter = ("service_type", "restricted")


admin.site.register(AgronomicCase)
admin.site.register(AdvisoryDispatch)
@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "farmer", "field", "channel", "status", "updated_at")
    list_filter = ("channel", "status")
admin.site.register(Message)
