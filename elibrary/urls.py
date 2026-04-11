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

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
