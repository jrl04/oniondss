from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import AdvisoryViewSet, ConversationViewSet, FieldViewSet, FarmerTokenAuth, api_root, app_message, sms_inbound, sms_status
router = DefaultRouter()
router.register("fields", FieldViewSet, basename="field")
router.register("advisories", AdvisoryViewSet, basename="advisory")
router.register("conversations", ConversationViewSet, basename="conversation")
urlpatterns = [path("", api_root, name="api-root"), path("auth/token/", FarmerTokenAuth.as_view(), name="api-token-auth"), path("messages/", app_message, name="app-message"), path("webhooks/sms/inbound/", sms_inbound), path("webhooks/sms/status/", sms_status), path("", include(router.urls))]
