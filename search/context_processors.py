from theses.models import Thesis


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

    return {
        "search_course_options": courses,
        "search_suggestions": search_suggestions,
    }