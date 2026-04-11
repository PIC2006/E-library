import threading
import logging

from django.contrib import messages
from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Count
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView

from .forms import ThesisUploadForm
from .models import Author, Download, Keyword, Thesis
from .tasks import build_thesis_previews, extract_thesis_text, process_thesis_upload


logger = logging.getLogger(__name__)


def _process_upload_background(thesis_id):
    thesis = Thesis.objects.get(pk=thesis_id)
    extract_thesis_text(thesis)
    build_thesis_previews(thesis)


def queue_or_process_thesis_upload(thesis):
    thesis_id = str(thesis.id)

    def _enqueue_processing():
        try:
            process_thesis_upload.delay(thesis_id)
        except Exception:
            # Keep request fast if broker is unavailable; process in background thread.
            logger.exception("Celery broker unavailable while queuing thesis upload %s; using thread fallback", thesis_id)
            threading.Thread(target=_process_upload_background, args=(thesis.id,), daemon=True).start()

    transaction.on_commit(_enqueue_processing)


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
        years = Thesis.objects.filter(is_public=True, status=Thesis.Status.APPROVED).values_list('year', flat=True).distinct().order_by('-year')
        context['years_list'] = sorted(set(years), reverse=True)
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

        raw_text = (thesis.search_document or "").strip()
        normalized_text = " ".join(raw_text.split())
        context["pdf_intro"] = " ".join(normalized_text.split()[:120]) if normalized_text else ""
        context["pdf_excerpt_available"] = bool(context["pdf_intro"])

        context["pdf_file_name"] = thesis.pdf_file.name.split("/")[-1] if thesis.pdf_file else "Unknown"
        context["pdf_preview_count"] = thesis.previews.count()
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
        response = super().form_valid(form)
        author_names = [name.strip() for name in form.cleaned_data["author_names"].split(",") if name.strip()]
        keyword_names = [name.strip() for name in form.cleaned_data.get("keyword_names", "").split(",") if name.strip()]

        self.object.authors.set(_get_or_create_authors(author_names))
        self.object.keywords.set(_get_or_create_keywords(keyword_names))
        queue_or_process_thesis_upload(self.object)
        messages.success(self.request, "Thesis uploaded and published.")
        return response


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
        thesis.increment_download_count()
        Download.objects.create(
            thesis=thesis,
            user=request.user if request.user.is_authenticated else None,
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        if not thesis.pdf_file:
            raise Http404("PDF file not found.")

        thesis.pdf_file.open("rb")
        response = FileResponse(thesis.pdf_file, as_attachment=True, filename=thesis.pdf_file.name.split("/")[-1])
        response["Content-Disposition"] = f'attachment; filename="{thesis.pdf_file.name.split("/")[-1]}"'
        return response
