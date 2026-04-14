import uuid

from django.conf import settings
from django.db import models
from django.db.models import F
from django.utils import timezone


class Course(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=40, blank=True)
    department = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Author(models.Model):
    full_name = models.CharField(max_length=150, unique=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class Keyword(models.Model):
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Thesis(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, db_index=True)
    abstract = models.TextField()
    pdf_file = models.FileField(upload_to="theses/%Y/%m/")
    file_hash = models.CharField(max_length=64, blank=True, db_index=True, help_text="SHA256 hash of the PDF file for duplicate detection")
    preview_page = models.PositiveIntegerField(default=1)
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="theses")
    year = models.PositiveIntegerField(db_index=True, blank=True, null=True)
    authors = models.ManyToManyField(Author, related_name="theses")
    keywords = models.ManyToManyField(Keyword, related_name="theses", blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="uploaded_theses")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_theses")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    is_public = models.BooleanField(default=False)
    download_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "year"]),
            models.Index(fields=["title"]),
        ]
    search_document = models.TextField(blank=True)

    def __str__(self):
        return self.display_title

    @property
    def display_title(self):
        return self.title or self.source_label or self.source_url or "Untitled source"

    def save(self, *args, **kwargs):
        if not self.title:
            self.title = self.source_label or self.source_url or "Untitled source"
        super().save(*args, **kwargs)

    def approve(self, approved_by):
        self.status = self.Status.APPROVED
        self.is_public = True
        self.approved_by = approved_by
        self.published_at = timezone.now()
        self.save(update_fields=["status", "is_public", "approved_by", "published_at", "updated_at"])

    def reject(self, approved_by):
        self.status = self.Status.REJECTED
        self.approved_by = approved_by
        self.is_public = False
        self.save(update_fields=["status", "is_public", "approved_by", "updated_at"])

    def increment_download_count(self):
        Thesis.objects.filter(pk=self.pk).update(download_count=F("download_count") + 1)
        self.refresh_from_db(fields=["download_count"])


class ThesisPreview(models.Model):
    thesis = models.ForeignKey(Thesis, on_delete=models.CASCADE, related_name="previews")
    page_number = models.PositiveIntegerField()
    preview_file = models.FileField(upload_to="thesis_previews/%Y/%m/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["page_number"]
        unique_together = ["thesis", "page_number"]

    def __str__(self):
        return f"{self.thesis.title} page {self.page_number}"


class Download(models.Model):
    thesis = models.ForeignKey(Thesis, on_delete=models.CASCADE, related_name="downloads")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="downloads")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Bookmark(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookmarks")
    thesis = models.ForeignKey(Thesis, on_delete=models.CASCADE, related_name="bookmarked_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["user", "thesis"]
        ordering = ["-created_at"]


class ApprovalLog(models.Model):
    class Action(models.TextChoices):
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    thesis = models.ForeignKey(Thesis, on_delete=models.CASCADE, related_name="approval_logs")
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="approval_actions")
    action = models.CharField(max_length=20, choices=Action.choices)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
