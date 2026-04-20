from django.urls import path

from .views import (
    AdminLoginView,
    CustomLogoutView,
    ProfileView,
    StaffUserDeleteView,
    StaffUserToggleActiveView,
    UserLoginView,
    UserRegistrationView,
)

urlpatterns = [
    path("login/", UserLoginView.as_view(), name="login"),
    path("register/", UserRegistrationView.as_view(), name="register"),
    path("admin-login/", AdminLoginView.as_view(), name="admin-login"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("logout/", CustomLogoutView.as_view(next_page="home"), name="logout"),
    path("staff/users/<int:pk>/toggle-active/", StaffUserToggleActiveView.as_view(), name="staff-user-toggle-active"),
    path("staff/users/<int:pk>/delete/", StaffUserDeleteView.as_view(), name="staff-user-delete"),
]
