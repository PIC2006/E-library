from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (("Role data", {"fields": ("role", "department", "phone_number", "profile_picture", "is_approved")}),)
    list_display = ["username", "email", "role", "is_approved", "is_staff", "is_active"]
    list_filter = ["role", "is_approved", "is_staff", "is_superuser", "is_active"]
    search_fields = ["username", "email", "first_name", "last_name"]
