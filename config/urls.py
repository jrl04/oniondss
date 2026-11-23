from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from messaging.views import home, officer_inbox
from messaging.field_map import field_map, ndvi_layer, vector_layer
urlpatterns = [path("", home, name="home"), path("admin/", admin.site.urls), path("officer/", officer_inbox, name="officer-inbox"), path("api/", include("messaging.urls"))]
if settings.DEBUG: urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += [
    path("fields/map/", field_map, name="field-map"),
    path("fields/map/ndvi/", ndvi_layer, name="ndvi-layer"),
    path("fields/map/layers/<str:name>/", vector_layer, name="field-map-vector"),
]
