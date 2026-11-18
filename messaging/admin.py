from django.contrib import admin
from .models import Advisory, Conversation, Field, Farmer, Message
@admin.register(Farmer)
class FarmerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "phone_verified", "sms_opt_in", "language")
    search_fields = ("name", "phone")
admin.site.register(Field)
admin.site.register(Advisory)
@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "farmer", "field", "channel", "status", "updated_at")
    list_filter = ("channel", "status")
admin.site.register(Message)
