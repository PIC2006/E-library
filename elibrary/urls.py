import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("theses.urls")),
    path("accounts/", include("accounts.urls")),
    path("search/", include("search.urls")),
    path("service/", include("theses.api_urls")),
    path("service/accounts/", include("accounts.api_urls")),
    path("service/search/", include("search.api_urls")),
]

serve_media = settings.DEBUG or (not getattr(settings, "USE_S3", False) and os.getenv("DJANGO_SERVE_MEDIA", "1") == "1")
if serve_media:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
