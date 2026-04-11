from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api_views import AnalyticsAPIView, ThesisViewSet

router = DefaultRouter()
router.register("theses", ThesisViewSet, basename="api-thesis")

urlpatterns = [
    path("", include(router.urls)),
    path("analytics/", AnalyticsAPIView.as_view(), name="api-analytics"),
]
