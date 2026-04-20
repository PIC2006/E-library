from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError

from theses.models import Thesis

from .models import LibrarySource


def search_ui_context(request):
    public_theses = Thesis.objects.filter(is_public=True, status=Thesis.Status.APPROVED)

    courses = list(
        public_theses.values_list("course__id", "course__name").distinct().order_by("course__name")
    )

    title_suggestions = list(
        public_theses.values_list("title", flat=True).distinct().order_by("title")[:40]
    )
    author_suggestions = list(
        public_theses.values_list("authors__full_name", flat=True)
        .exclude(authors__full_name__isnull=True)
        .exclude(authors__full_name="")
        .distinct()
        .order_by("authors__full_name")[:40]
    )
    keyword_suggestions = list(
        public_theses.values_list("keywords__name", flat=True)
        .exclude(keywords__name__isnull=True)
        .exclude(keywords__name="")
        .distinct()
        .order_by("keywords__name")[:40]
    )

    search_suggestions = []
    for item in title_suggestions + author_suggestions + keyword_suggestions:
        if item and item not in search_suggestions:
            search_suggestions.append(item)
        if len(search_suggestions) >= 60:
            break

    external_sources = []
    try:
        external_sources = [
            {
                "label": source.label,
                "url": source.url,
                "category": source.category,
            }
            for source in LibrarySource.objects.filter(is_active=True).order_by("sort_order", "label")
        ]
    except (OperationalError, ProgrammingError):
        external_sources = []

    if not external_sources:
        external_sources = [item for item in getattr(settings, "ELIBRARY_SOURCE_LINKS", []) if item.get("url")]

    is_admin_user = request.user.is_authenticated and (
        request.user.is_staff or request.user.is_superuser or getattr(request.user, "role", None) == "admin"
    )

    if not request.user.is_authenticated:
        external_sources = [source for source in external_sources if source.get("category") != "gdrive"]

    return {
        "search_course_options": courses,
        "search_suggestions": search_suggestions,
        "elibrary_external_sources": external_sources,
        "is_admin_user": is_admin_user,
        "debug_enabled": settings.DEBUG,
    }