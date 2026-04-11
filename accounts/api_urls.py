from django.urls import path

from .views import MeAPIView

urlpatterns = [
    path("me/", MeAPIView.as_view(), name="api-me"),
]
