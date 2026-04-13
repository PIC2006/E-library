from django.urls import path

from .views import AdminHomeView, AnalyticsDashboardView, ThesisDeleteView, ThesisDetailView, ThesisDownloadView, ThesisEditView, ThesisListView, ThesisPDFView, ThesisUploadView

urlpatterns = [
    path("", ThesisListView.as_view(), name="home"),
    path("theses/", ThesisListView.as_view(), name="thesis-list"),
    path("theses/upload/", ThesisUploadView.as_view(), name="thesis-upload"),
    path("theses/<uuid:pk>/", ThesisDetailView.as_view(), name="thesis-detail"),
    path("theses/<uuid:pk>/edit/", ThesisEditView.as_view(), name="thesis-edit"),
    path("theses/<uuid:pk>/delete/", ThesisDeleteView.as_view(), name="thesis-delete"),
    path("theses/<uuid:pk>/pdf/", ThesisPDFView.as_view(), name="thesis-pdf"),
    path("theses/<uuid:pk>/download/", ThesisDownloadView.as_view(), name="thesis-download"),
    path("staff/", AdminHomeView.as_view(), name="admin-home"),
    path("staff/dashboard/", AnalyticsDashboardView.as_view(), name="dashboard"),
]
