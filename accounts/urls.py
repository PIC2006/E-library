from django.urls import path

from .views import AdminLoginView, CustomLogoutView, ProfileView, UserLoginView, UserRegistrationView

urlpatterns = [
    path("login/", UserLoginView.as_view(), name="login"),
    path("register/", UserRegistrationView.as_view(), name="register"),
    path("admin-login/", AdminLoginView.as_view(), name="admin-login"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("logout/", CustomLogoutView.as_view(next_page="home"), name="logout"),
]
