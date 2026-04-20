from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView
from rest_framework.response import Response
from rest_framework.views import APIView

from .forms import StyledAuthenticationForm, UserLoginForm, UserRegistrationForm
from .serializers import UserSerializer


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


class MeAPIView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)
