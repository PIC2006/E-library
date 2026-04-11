from django.urls import path

from .views import AdvancedSearchAPIView

urlpatterns = [
    path("advanced/", AdvancedSearchAPIView.as_view(), name="api-search-advanced"),
]
