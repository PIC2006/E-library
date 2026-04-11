from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from rest_framework.response import Response
from rest_framework.views import APIView

from .forms import StyledAuthenticationForm
from .serializers import UserSerializer


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
