from rest_framework import serializers
from .models import Advisory, Conversation, Field, Message, SpatialLayer

class FieldSerializer(serializers.ModelSerializer):
    class Meta: model = Field; fields = ["id", "code", "name", "crop", "season", "area_ha", "geometry_revision"]


class AdvisorySerializer(serializers.ModelSerializer):
    field_code = serializers.CharField(source="field.code", read_only=True)
    class Meta: model = Advisory; fields = ["id", "field", "field_code", "topic", "language", "title", "body", "published_at", "effective_to", "scheduled_at"]


class SpatialLayerSerializer(serializers.ModelSerializer):
    field_code = serializers.CharField(source="field.code", read_only=True)

    class Meta:
        model = SpatialLayer
        fields = ["id", "field", "field_code", "name", "service_type", "service_url", "layer_name", "style_name", "cache_version", "published_at"]


class MessageSerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()
    class Meta: model = Message; fields = ["id", "direction", "body", "channel", "delivery_status", "processing_status", "intent", "created_at", "photo_url"]

    def get_photo_url(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.photo.url) if request and obj.photo else None


class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    field_code = serializers.CharField(source="field.code", read_only=True, allow_null=True)
    farmer_name = serializers.CharField(source="farmer.name", read_only=True)
    case_status = serializers.SerializerMethodField()

    def get_case_status(self, obj):
        case = getattr(obj, "case", None)
        return case.status if case else None

    class Meta: model = Conversation; fields = ["id", "farmer_name", "field", "field_code", "channel", "language", "status", "case_status", "subject", "updated_at", "messages"]
