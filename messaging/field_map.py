import logging

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .models import Field

logger = logging.getLogger(__name__)
NDVI_COLORS = ["a33a2b", "e8ae51", "f2edac", "66aa62", "17583b"]


@staff_member_required
@never_cache
@require_GET
def field_map(request):
    fields = Field.objects.select_related("farmer").order_by("farmer__name", "code")
    records = [
        {
            "id": field.pk,
            "code": field.code,
            "name": field.name,
            "farmer": field.farmer.name,
            "geometry": field.boundary,
        }
        for field in fields
    ]
    return render(request, "messaging/field_map.html", {
        "field_records": records,
        "ndvi_colors": NDVI_COLORS,
    })


def get_ndvi_tile_url(project, asset, band):
    import ee

    ee.Initialize(project=project)
    image = ee.Image(asset).select(band)
    layer = image.getMapId({"min": -1, "max": 1, "palette": NDVI_COLORS})
    return layer["tile_fetcher"].url_format


@staff_member_required
@never_cache
@require_GET
def ndvi_layer(request):
    project = settings.EARTH_ENGINE_PROJECT
    asset = settings.EARTH_ENGINE_NDVI_ASSET
    band = settings.EARTH_ENGINE_NDVI_BAND
    if not project or not asset:
        return JsonResponse({"detail": "Set the Earth Engine project and NDVI asset to display the raster."}, status=503)
    try:
        url = cache.get_or_set(
            f"field-map:ndvi:{project}:{asset}:{band}",
            lambda: get_ndvi_tile_url(project, asset, band),
            timeout=120,
        )
    except Exception:
        logger.exception("Could not load the configured Earth Engine NDVI layer")
        return JsonResponse({"detail": "Earth Engine could not load the NDVI raster. Check project access, asset ID, and band name."}, status=502)
    return JsonResponse({"tile_url": url})
