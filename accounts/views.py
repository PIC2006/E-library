from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, TemplateView
from rest_framework.response import Response
from rest_framework.views import APIView

from .forms import StyledAuthenticationForm, UserLoginForm, UserRegistrationForm
from .serializers import UserSerializer


def _is_admin_user(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser or getattr(user, "role", None) == "admin")


class UserLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = UserLoginForm
    redirect_authenticated_user = True


class UserRegistrationView(CreateView):
    template_name = "accounts/register.html"
    form_class = UserRegistrationForm
    success_url = reverse_lazy("home")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.success(self.request, "Account created. Welcome to E-Library.")
        return response


class ProfileView(TemplateView):
    template_name = "accounts/profile.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Local import avoids circular dependency at module import time.
        from theses.models import Bookmark, Download

        user = self.request.user
        context["bookmark_items"] = (
            Bookmark.objects.filter(user=user)
            .select_related("thesis", "thesis__course")
            .order_by("-created_at")
        )
        context["recent_downloads"] = (
            Download.objects.filter(user=user)
            .select_related("thesis", "thesis__course")
            .order_by("-created_at")[:10]
        )
        context["total_downloads"] = Download.objects.filter(user=user).count()
        return context


class AdminLoginView(LoginView):
    template_name = "accounts/admin_login.html"
    authentication_form = StyledAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy("admin-home")


class CustomLogoutView(LogoutView):
    http_method_names = ['post', 'get', 'options']


class StaffOnlyMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return _is_admin_user(self.request.user)


class StaffUserToggleActiveView(StaffOnlyMixin, View):
    def post(self, request, pk, *args, **kwargs):
        user = get_object_or_404(get_user_model(), pk=pk)
        if user.pk == request.user.pk:
            messages.warning(request, "You cannot change your own active status from this page.")
            return redirect("admin-home")

        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])

        status_text = "restored" if user.is_active else "banned"
        messages.success(request, f"{user.username} has been {status_text}.")
        return redirect("admin-home")


class StaffUserDeleteView(StaffOnlyMixin, View):
    def post(self, request, pk, *args, **kwargs):
        user = get_object_or_404(get_user_model(), pk=pk)
        if user.pk == request.user.pk:
            messages.warning(request, "You cannot delete your own account from this page.")
            return redirect("admin-home")

        username = user.username
        user.delete()
        messages.success(request, f"{username} has been deleted.")
        return redirect("admin-home")


class MeAPIView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)
