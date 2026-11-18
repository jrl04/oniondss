from rest_framework import serializers
from .models import Advisory, Conversation, Field, Message

class FieldSerializer(serializers.ModelSerializer):
    class Meta: model = Field; fields = ["id", "code", "name", "crop", "area_ha"]
class AdvisorySerializer(serializers.ModelSerializer):
    field_code = serializers.CharField(source="field.code", read_only=True)
    class Meta: model = Advisory; fields = ["id", "field_code", "title", "body", "published_at"]
class MessageSerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()
    class Meta: model = Message; fields = ["id", "direction", "body", "channel", "delivery_status", "created_at", "photo_url"]
    def get_photo_url(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.photo.url) if request and obj.photo else None
class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    field_code = serializers.CharField(source="field.code", read_only=True, allow_null=True)
    farmer_name = serializers.CharField(source="farmer.name", read_only=True)
    class Meta: model = Conversation; fields = ["id", "farmer_name", "field", "field_code", "channel", "status", "subject", "updated_at", "messages"]
