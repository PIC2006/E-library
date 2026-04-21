from django.contrib import messages
from django.contrib.auth import logout
from django.urls import Resolver404, resolve


class RequireApprovedAccountMiddleware:
    """Prevent pending users from accessing the app until approved by staff."""

    EXEMPT_URL_NAMES = {"login", "logout", "register", "admin-login"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            is_admin = user.is_staff or user.is_superuser or getattr(user, "role", None) == "admin"
            if not is_admin and not getattr(user, "is_approved", False):
                try:
                    match = resolve(request.path_info)
                    url_name = match.url_name
                except Resolver404:
                    url_name = None

                if url_name not in self.EXEMPT_URL_NAMES:
                    logout(request)
                    messages.warning(
                        request,
                        "Your account is still pending admin approval. Please try again after approval.",
                    )

        return self.get_response(request)
