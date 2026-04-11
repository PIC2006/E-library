from django.db import connection
from django.db.models import Q
from django.db.models.functions import Lower
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.shortcuts import render
from django.views.generic import ListView, TemplateView
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from theses.models import Thesis
from theses.serializers import ThesisListSerializer


class SearchView(ListView):
    model = Thesis
    template_name = "search/results.html"
    context_object_name = "results"
    paginate_by = 10

    def get_queryset(self):
        query = self.request.GET.get("q", "").strip()
        title = self.request.GET.get("title", "").strip()
        author = self.request.GET.get("author", "").strip()
        keyword = self.request.GET.get("keyword", "").strip()
        course = self.request.GET.get("course", "").strip()
        course_id = self.request.GET.get("course_id", "").strip()
        year = self.request.GET.get("year", "").strip()
        queryset = Thesis.objects.filter(is_public=True, status=Thesis.Status.APPROVED).select_related("course").prefetch_related("authors", "keywords")
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(abstract__icontains=query)
                | Q(authors__full_name__icontains=query)
                | Q(keywords__name__icontains=query)
            )
        if title:
            queryset = queryset.filter(title__icontains=title)
        if author:
            queryset = queryset.filter(authors__full_name__icontains=author)
        if keyword:
            queryset = queryset.filter(keywords__name__icontains=keyword)
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        elif course:
            queryset = queryset.filter(course__name__icontains=course)
        if year:
            queryset = queryset.filter(year=year)
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Generate list of years from oldest to newest
        years = Thesis.objects.filter(is_public=True, status=Thesis.Status.APPROVED).values_list('year', flat=True).distinct().order_by('-year')
        context['years_list'] = sorted(set(years), reverse=True)
        return context


class AdvancedSearchAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        queryset = Thesis.objects.filter(is_public=True, status=Thesis.Status.APPROVED).select_related("course").prefetch_related("authors", "keywords")
        query = request.query_params.get("q", "").strip()
        if connection.vendor == "postgresql" and query:
            vector = SearchVector("title", weight="A") + SearchVector("abstract", weight="B") + SearchVector("search_document", weight="C")
            queryset = queryset.annotate(rank=SearchRank(vector, SearchQuery(query))).filter(rank__gte=0.05).order_by("-rank")
        elif query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(abstract__icontains=query)
                | Q(authors__full_name__icontains=query)
                | Q(keywords__name__icontains=query)
                | Q(search_document__icontains=query)
            ).distinct()
        title = request.query_params.get("title")
        author = request.query_params.get("author")
        keyword = request.query_params.get("keyword")
        course = request.query_params.get("course")
        year = request.query_params.get("year")
        if title:
            queryset = queryset.filter(title__icontains=title)
        if author:
            queryset = queryset.filter(authors__full_name__icontains=author)
        if keyword:
            queryset = queryset.filter(keywords__name__icontains=keyword)
        if course:
            queryset = queryset.filter(course__name__icontains=course)
        if year:
            queryset = queryset.filter(year=year)
        data = ThesisListSerializer(queryset.distinct(), many=True, context={"request": request}).data
        return Response({"results": data, "count": len(data)})
