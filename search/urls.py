from django.urls import path

from .views import LibrarySourceCreateView, SearchView

urlpatterns = [
    path("", SearchView.as_view(), name="search"),
    path("sources/add/", LibrarySourceCreateView.as_view(), name="library-source-add"),
]
