from django.contrib import admin

from .models import LibrarySource


@admin.register(LibrarySource)
class LibrarySourceAdmin(admin.ModelAdmin):
    list_display = ["label", "category", "is_active", "sort_order"]
    list_filter = ["category", "is_active"]
    search_fields = ["label", "url"]
    list_editable = ["is_active", "sort_order"]