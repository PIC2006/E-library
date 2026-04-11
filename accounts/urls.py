from django.urls import path

from .views import AdminLoginView, CustomLogoutView

urlpatterns = [
    path("admin-login/", AdminLoginView.as_view(), name="admin-login"),
    path("logout/", CustomLogoutView.as_view(next_page="home"), name="logout"),
]
