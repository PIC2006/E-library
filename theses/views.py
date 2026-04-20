import logging
import hashlib
import os
import threading
from urllib.parse import quote

from django.contrib import messages
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Count
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from .forms import ThesisUploadForm
from .models import Author, Bookmark, Download, Keyword, Thesis
from .tasks import process_thesis_upload


logger = logging.getLogger(__name__)
GUEST_DOWNLOAD_LIMIT = 5


def _get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _calculate_file_hash(pdf_file):
    """Calculate SHA256 hash of an uploaded PDF file"""
    pdf_file.seek(0)
    hash_obj = hashlib.sha256()
    for chunk in pdf_file.chunks(chunk_size=8192):
        hash_obj.update(chunk)
    pdf_file.seek(0)
    return hash_obj.hexdigest()
def _get_or_create_authors(author_names):
    if not author_names:
        return []

    unique_names = list(dict.fromkeys(author_names))
    existing = {author.full_name: author for author in Author.objects.filter(full_name__in=unique_names)}
    missing_names = [name for name in unique_names if name not in existing]

    if missing_names:
        Author.objects.bulk_create([Author(full_name=name) for name in missing_names], ignore_conflicts=True)

    author_map = {author.full_name: author for author in Author.objects.filter(full_name__in=unique_names)}
    return [author_map[name] for name in unique_names if name in author_map]


def _get_or_create_keywords(keyword_names):
    if not keyword_names:
        return []

    normalized_names = [name.lower() for name in keyword_names]
    unique_names = list(dict.fromkeys(normalized_names))
    existing = {keyword.name: keyword for keyword in Keyword.objects.filter(name__in=unique_names)}
    missing_names = [name for name in unique_names if name not in existing]

    if missing_names:
        Keyword.objects.bulk_create([Keyword(name=name) for name in missing_names], ignore_conflicts=True)

    keyword_map = {keyword.name: keyword for keyword in Keyword.objects.filter(name__in=unique_names)}
    return [keyword_map[name] for name in unique_names if name in keyword_map]


def _delete_thesis_media(thesis):
    if thesis.pdf_file:
        thesis.pdf_file.delete(save=False)

    for preview in thesis.previews.all():
        if preview.preview_file:
            preview.preview_file.delete(save=False)


def _enqueue_pdf_processing(thesis_id):
    try:
        process_thesis_upload.delay(str(thesis_id))
    except Exception:
        logger.exception("Celery broker unavailable while processing thesis %s; using thread fallback", thesis_id)
        threading.Thread(target=process_thesis_upload, args=(str(thesis_id),), daemon=True).start()


class ThesisListView(ListView):
    model = Thesis
    template_name = "theses/list.html"
    context_object_name = "theses"
    paginate_by = 10

    def get_queryset(self):
        return Thesis.objects.filter(is_public=True, status=Thesis.Status.APPROVED).select_related("course", "uploaded_by").prefetch_related("authors", "keywords")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Generate list of years from oldest to newest
        years = (
            Thesis.objects.filter(is_public=True, status=Thesis.Status.APPROVED)
            .exclude(year__isnull=True)
            .values_list('year', flat=True)
            .distinct()
            .order_by('-year')
        )
        context['years_list'] = list(years)
        return context


class ThesisDetailView(DetailView):
    model = Thesis
    template_name = "theses/detail.html"
    context_object_name = "thesis"

    def get_queryset(self):
        queryset = Thesis.objects.select_related("course", "uploaded_by", "approved_by").prefetch_related("authors", "keywords", "previews")
        user = self.request.user
        if user.is_authenticated and (user.is_staff or user.is_superuser or getattr(user, "role", None) == "admin"):
            return queryset
        return queryset.filter(is_public=True, status=Thesis.Status.APPROVED)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        thesis = self.object
        user = self.request.user
        can_manage = user.is_authenticated and (
            user == thesis.uploaded_by or user.is_staff or user.is_superuser or getattr(user, "role", None) == "admin"
        )

        if can_manage:
            context["edit_form"] = ThesisUploadForm(
                instance=thesis,
                initial={
                    "author_names": ", ".join(thesis.authors.values_list("full_name", flat=True)),
                    "keyword_names": ", ".join(thesis.keywords.values_list("name", flat=True)),
                },
            )
        context["can_manage"] = can_manage
        context["is_bookmarked"] = user.is_authenticated and Bookmark.objects.filter(user=user, thesis=thesis).exists()

        raw_text = (thesis.search_document or "").strip()
        normalized_text = " ".join(raw_text.split())
        context["pdf_intro"] = " ".join(normalized_text.split()[:120]) if normalized_text else ""
        context["pdf_excerpt_available"] = bool(context["pdf_intro"])

        context["pdf_file_name"] = thesis.pdf_file.name.split("/")[-1] if thesis.pdf_file else "Unknown"
        preview_items = [
            preview
            for preview in thesis.previews.all()
            if preview.preview_file and preview.preview_file.storage.exists(preview.preview_file.name)
        ]
        context["preview_items"] = preview_items
        context["pdf_preview_count"] = len(preview_items)
        context["pdf_extracted_chars"] = len(raw_text)
        size_label = "Unavailable"
        if thesis.pdf_file:
            try:
                size_bytes = thesis.pdf_file.size
                if size_bytes >= 1024 * 1024:
                    size_label = f"{size_bytes / (1024 * 1024):.2f} MB"
                else:
                    size_label = f"{size_bytes / 1024:.1f} KB"
            except Exception:
                size_label = "Unavailable"
        context["pdf_file_size"] = size_label
        return context


class ThesisPDFView(DetailView):
    model = Thesis
    template_name = "theses/pdf_view.html"
    context_object_name = "thesis"

    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Thesis.objects.select_related("course", "uploaded_by", "approved_by").prefetch_related("authors", "keywords", "previews")
        user = self.request.user
        if user.is_authenticated and (user.is_staff or user.is_superuser or getattr(user, "role", None) == "admin"):
            return queryset
        if user.is_authenticated:
            return queryset.filter(models.Q(is_public=True, status=Thesis.Status.APPROVED) | models.Q(uploaded_by=user))
        return queryset.filter(is_public=True, status=Thesis.Status.APPROVED)


class ThesisUploadView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Thesis
    form_class = ThesisUploadForm
    template_name = "theses/upload.html"
    success_url = reverse_lazy("thesis-list")

    def test_func(self):
        user = self.request.user
        return user.is_staff or user.is_superuser or getattr(user, "role", None) == "admin"

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        messages.error(self.request, "Only admins can upload theses.")
        return redirect("home")

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        form.instance.status = Thesis.Status.APPROVED
        form.instance.is_public = True
        form.instance.approved_by = self.request.user
        form.instance.published_at = timezone.now()
        form.instance.file_hash = _calculate_file_hash(form.cleaned_data["pdf_file"])
        response = super().form_valid(form)
        author_names = [name.strip() for name in form.cleaned_data["author_names"].split(",") if name.strip()]
        keyword_names = [name.strip() for name in form.cleaned_data.get("keyword_names", "").split(",") if name.strip()]

        self.object.authors.set(_get_or_create_authors(author_names))
        self.object.keywords.set(_get_or_create_keywords(keyword_names))
        messages.success(self.request, "Thesis uploaded and published.")
        return response


class ThesisEditView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Thesis
    form_class = ThesisUploadForm
    template_name = "theses/edit.html"
    
    def test_func(self):
        thesis = self.get_object()
        user = self.request.user
        is_admin = user.is_staff or user.is_superuser or getattr(user, "role", None) == "admin"
        is_uploader = thesis.uploaded_by == user
        return is_admin or is_uploader

    def handle_no_permission(self):
        messages.error(self.request, "You don't have permission to edit this thesis.")
        return redirect("thesis-detail", pk=self.kwargs.get("pk"))

    def get_success_url(self):
        return reverse_lazy("thesis-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        # Calculate new file hash if file was changed
        if "pdf_file" in form.changed_data and form.cleaned_data["pdf_file"]:
            form.instance.file_hash = _calculate_file_hash(form.cleaned_data["pdf_file"])
        
        response = super().form_valid(form)
        
        # Update authors and keywords
        author_names = [name.strip() for name in form.cleaned_data["author_names"].split(",") if name.strip()]
        keyword_names = [name.strip() for name in form.cleaned_data.get("keyword_names", "").split(",") if name.strip()]
        
        self.object.authors.set(_get_or_create_authors(author_names))
        self.object.keywords.set(_get_or_create_keywords(keyword_names))
        
        
        messages.success(self.request, "Thesis updated successfully.")
        return response


class ThesisDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Thesis
    template_name = "theses/delete.html"
    success_url = reverse_lazy("thesis-list")

    def test_func(self):
        thesis = self.get_object()
        user = self.request.user
        is_admin = user.is_staff or user.is_superuser or getattr(user, "role", None) == "admin"
        is_uploader = thesis.uploaded_by == user
        return is_admin or is_uploader

    def handle_no_permission(self):
        messages.error(self.request, "You don't have permission to delete this thesis.")
        return redirect("thesis-detail", pk=self.kwargs.get("pk"))

    def form_valid(self, form):
        thesis = self.get_object()
        _delete_thesis_media(thesis)
        messages.success(self.request, "Thesis deleted successfully.")
        return super().form_valid(form)


class ThesisBulkDeleteView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser or getattr(self.request.user, "role", None) == "admin"

    def post(self, request, *args, **kwargs):
        thesis_ids = request.POST.getlist("thesis_ids")
        if not thesis_ids:
            messages.warning(request, "Select at least one thesis to delete.")
            return redirect("admin-home")

        theses = Thesis.objects.filter(pk__in=thesis_ids)
        deleted_count = 0

        for thesis in theses:
            _delete_thesis_media(thesis)
            thesis.delete()
            deleted_count += 1

        messages.success(request, f"Deleted {deleted_count} thesis record(s).")
        return redirect("admin-home")


class ThesisProcessLaterView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser or getattr(self.request.user, "role", None) == "admin"

    def post(self, request, *args, **kwargs):
        thesis_id = request.POST.get("thesis_id")
        if not thesis_id:
            messages.warning(request, "No thesis selected for processing.")
            return redirect("admin-home")

        thesis = get_object_or_404(Thesis, pk=thesis_id)
        _enqueue_pdf_processing(thesis.pk)
        messages.success(request, f"Queued PDF processing for: {thesis.title}")
        return redirect("admin-home")


class AdminHomeView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "theses/admin_home.html"

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser or getattr(self.request.user, "role", None) == "admin"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "").strip()
        course_id = self.request.GET.get("course_id", "").strip()
        year = self.request.GET.get("year", "").strip()
        recent_page_number = self.request.GET.get("recent_page", "1")

        approved_theses = Thesis.objects.filter(status=Thesis.Status.APPROVED).select_related("course", "uploaded_by").prefetch_related("authors", "keywords")

        if query:
            approved_theses = approved_theses.filter(
                models.Q(title__icontains=query)
                | models.Q(abstract__icontains=query)
                | models.Q(authors__full_name__icontains=query)
                | models.Q(keywords__name__icontains=query)
                | models.Q(course__name__icontains=query)
            )

        if course_id:
            approved_theses = approved_theses.filter(course_id=course_id)

        if year:
            try:
                year_int = int(year)
                approved_theses = approved_theses.filter(year=year_int)
            except ValueError:
                pass

        context["thesis_count"] = Thesis.objects.count()
        context["approved_count"] = Thesis.objects.filter(status=Thesis.Status.APPROVED).count()
        context["private_count"] = Thesis.objects.filter(is_public=False).count()

        recent_uploads_qs = Thesis.objects.order_by("-created_at").select_related("course", "uploaded_by")
        recent_uploads_paginator = Paginator(recent_uploads_qs, 5)
        recent_uploads_page = recent_uploads_paginator.get_page(recent_page_number)

        context["recent_uploads"] = recent_uploads_page.object_list
        context["recent_uploads_page"] = recent_uploads_page
        context["approved_theses"] = approved_theses.distinct().order_by("-created_at")[:15]
        context["admin_query"] = query
        context["admin_course_id"] = course_id
        context["admin_year"] = year
        context["total_downloads"] = Download.objects.count()
        context["total_users"] = get_user_model().objects.count()
        return context


class AnalyticsDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "theses/dashboard.html"

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser or getattr(self.request.user, "role", None) == "admin"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["thesis_count"] = Thesis.objects.count()
        context["pending_count"] = Thesis.objects.filter(status=Thesis.Status.PENDING).count()
        context["approved_count"] = Thesis.objects.filter(status=Thesis.Status.APPROVED).count()
        context["download_leaders"] = Thesis.objects.filter(is_public=True).order_by("-download_count")[:5]
        context["downloads_by_course"] = (
            Thesis.objects.values("course__name").annotate(total=Count("downloads")).order_by("-total")[:5]
        )
        return context


class ThesisDownloadView(View):
    def get_object(self):
        return get_object_or_404(Thesis, pk=self.kwargs["pk"], is_public=True, status=Thesis.Status.APPROVED)

    def get(self, request, *args, **kwargs):
        thesis = self.get_object()
        if not thesis.pdf_file:
            raise Http404("PDF file not found.")

        client_ip = _get_client_ip(request)
        if not request.user.is_authenticated:
            if client_ip:
                anonymous_downloads = Download.objects.filter(user__isnull=True, ip_address=client_ip).count()
            else:
                anonymous_downloads = request.session.get("guest_download_count", 0)
            if anonymous_downloads >= GUEST_DOWNLOAD_LIMIT:
                messages.warning(
                    request,
                    "Guest download limit reached (5 theses). Sign in or register for unlimited downloads.",
                )
                login_url = f"{reverse('login')}?next={quote(request.get_full_path())}"
                return redirect(login_url)

        file_name = thesis.pdf_file.name.split("/")[-1]

        try:
            file_path = thesis.pdf_file.path
        except (NotImplementedError, ValueError, OSError):
            file_path = None

        if file_path and os.path.exists(file_path):
            thesis.increment_download_count()
            Download.objects.create(
                thesis=thesis,
                user=request.user if request.user.is_authenticated else None,
                ip_address=client_ip,
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )

            if not request.user.is_authenticated and not client_ip:
                request.session["guest_download_count"] = request.session.get("guest_download_count", 0) + 1

            response = FileResponse(open(file_path, "rb"), as_attachment=True, filename=file_name)
            response["Content-Disposition"] = f'attachment; filename="{file_name}"'
            return response

        thesis.increment_download_count()
        Download.objects.create(
            thesis=thesis,
            user=request.user if request.user.is_authenticated else None,
            ip_address=client_ip,
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        if not request.user.is_authenticated and not client_ip:
            request.session["guest_download_count"] = request.session.get("guest_download_count", 0) + 1

        file_url = thesis.pdf_file.url
        if file_url.startswith("/"):
            file_url = request.build_absolute_uri(file_url)

        return HttpResponseRedirect(file_url)


class ThesisBookmarkToggleView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        thesis = get_object_or_404(Thesis, pk=self.kwargs["pk"], is_public=True, status=Thesis.Status.APPROVED)
        bookmark, created = Bookmark.objects.get_or_create(user=request.user, thesis=thesis)
        if not created:
            bookmark.delete()
            messages.info(request, "Removed from your bookmarks.")
        else:
            messages.success(request, "Saved to your bookmarks.")

        next_url = request.POST.get("next")
        if next_url:
            return redirect(next_url)
        return redirect("thesis-detail", pk=thesis.pk)
