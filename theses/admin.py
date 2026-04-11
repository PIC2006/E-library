from django.contrib import admin

from .models import ApprovalLog, Author, Bookmark, Course, Download, Keyword, Thesis, ThesisPreview


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "department"]
    search_fields = ["name", "code", "department"]


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    search_fields = ["full_name"]


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Thesis)
class ThesisAdmin(admin.ModelAdmin):
    list_display = ["title", "course", "year", "status", "download_count", "created_at"]
    list_filter = ["status", "course", "year", "is_public"]
    search_fields = ["title", "abstract", "authors__full_name", "keywords__name"]
    filter_horizontal = ["authors", "keywords"]
    actions = ["approve_selected", "reject_selected"]

    def approve_selected(self, request, queryset):
        for thesis in queryset:
            thesis.approve(request.user)

    def reject_selected(self, request, queryset):
        for thesis in queryset:
            thesis.reject(request.user)


@admin.register(Download)
class DownloadAdmin(admin.ModelAdmin):
    list_display = ["thesis", "user", "ip_address", "created_at"]
    search_fields = ["thesis__title", "user__username", "ip_address"]


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ["user", "thesis", "created_at"]


@admin.register(ApprovalLog)
class ApprovalLogAdmin(admin.ModelAdmin):
    list_display = ["thesis", "admin", "action", "created_at"]


@admin.register(ThesisPreview)
class ThesisPreviewAdmin(admin.ModelAdmin):
    list_display = ["thesis", "page_number", "created_at"]
