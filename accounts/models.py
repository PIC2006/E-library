from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        STUDENT = "student", "Student"
        GUEST = "guest", "Guest"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    department = models.CharField(max_length=120, blank=True)
    phone_number = models.CharField(max_length=32, blank=True)
    is_approved = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to="profiles/%Y/%m/", blank=True, null=True)

    def is_admin_role(self):
        return self.role == self.Role.ADMIN or self.is_staff or self.is_superuser

    @property
    def profile_picture_safe_url(self):
        if not self.profile_picture:
            return ""

        name = getattr(self.profile_picture, "name", "")
        if not name:
            return ""

        try:
            if self.profile_picture.storage.exists(name):
                return self.profile_picture.url
        except Exception:
            return ""

        return ""
