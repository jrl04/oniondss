from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from messaging.views import home, officer_inbox
urlpatterns = [path("", home, name="home"), path("admin/", admin.site.urls), path("officer/", officer_inbox, name="officer-inbox"), path("api/", include("messaging.urls"))]
if settings.DEBUG: urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
