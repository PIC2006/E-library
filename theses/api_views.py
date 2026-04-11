from django.db.models import Count, Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ApprovalLog, Bookmark, Download, Thesis
from .serializers import DownloadSerializer, ThesisDetailSerializer, ThesisListSerializer, ThesisWriteSerializer


class ThesisViewSet(viewsets.ModelViewSet):
	queryset = Thesis.objects.select_related("course", "uploaded_by", "approved_by").prefetch_related("authors", "keywords", "approval_logs")
	permission_classes = [permissions.IsAuthenticatedOrReadOnly]
	lookup_field = "pk"

	def get_serializer_class(self):
		if self.action in ["create", "update", "partial_update"]:
			return ThesisWriteSerializer
		if self.action == "retrieve":
			return ThesisDetailSerializer
		return ThesisListSerializer

	def get_queryset(self):
		queryset = super().get_queryset()
		user = self.request.user
		if user.is_authenticated and (user.is_staff or user.is_superuser or getattr(user, "role", None) == "admin"):
			return queryset
		if user.is_authenticated:
			return queryset.filter(Q(is_public=True, status=Thesis.Status.APPROVED) | Q(uploaded_by=user))
		return queryset.filter(is_public=True, status=Thesis.Status.APPROVED)

	def _can_manage(self, thesis):
		user = self.request.user
		return user.is_authenticated and (
			user.is_staff or user.is_superuser or getattr(user, "role", None) == "admin" or thesis.uploaded_by_id == user.id
		)

	def perform_create(self, serializer):
		thesis = serializer.save(uploaded_by=self.request.user)
		from .tasks import process_thesis_upload

		process_thesis_upload.delay(str(thesis.id))

	def perform_update(self, serializer):
		thesis = serializer.instance
		if not self._can_manage(thesis):
			raise PermissionDenied("You cannot edit this thesis.")
		serializer.save()

	def perform_destroy(self, instance):
		if not self._can_manage(instance):
			raise PermissionDenied("You cannot delete this thesis.")
		instance.delete()

	@action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
	def bookmark(self, request, pk=None):
		thesis = self.get_object()
		bookmark, created = Bookmark.objects.get_or_create(user=request.user, thesis=thesis)
		if not created:
			bookmark.delete()
			return Response({"bookmarked": False})
		return Response({"bookmarked": True})

	@action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
	def download(self, request, pk=None):
		thesis = self.get_object()
		thesis.increment_download_count()
		download = Download.objects.create(
			thesis=thesis,
			user=request.user,
			ip_address=request.META.get("REMOTE_ADDR"),
			user_agent=request.META.get("HTTP_USER_AGENT", ""),
		)
		return Response({"download": DownloadSerializer(download).data, "file_url": thesis.pdf_file.url})

	@action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
	def approve(self, request, pk=None):
		thesis = self.get_object()
		if not request.user.is_staff and not request.user.is_superuser and getattr(request.user, "role", None) != "admin":
			return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)
		thesis.approve(request.user)
		ApprovalLog.objects.create(thesis=thesis, admin=request.user, action=ApprovalLog.Action.APPROVED, note=request.data.get("note", ""))
		return Response(ThesisDetailSerializer(thesis, context={"request": request}).data)

	@action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
	def reject(self, request, pk=None):
		thesis = self.get_object()
		if not request.user.is_staff and not request.user.is_superuser and getattr(request.user, "role", None) != "admin":
			return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)
		thesis.reject(request.user)
		ApprovalLog.objects.create(thesis=thesis, admin=request.user, action=ApprovalLog.Action.REJECTED, note=request.data.get("note", ""))
		return Response(ThesisDetailSerializer(thesis, context={"request": request}).data)


class AnalyticsAPIView(APIView):
	def get(self, request):
		if not request.user.is_authenticated:
			return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
		if not request.user.is_staff and not request.user.is_superuser and getattr(request.user, "role", None) != "admin":
			return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)
		data = {
			"thesis_count": Thesis.objects.count(),
			"pending_count": Thesis.objects.filter(status=Thesis.Status.PENDING).count(),
			"approved_count": Thesis.objects.filter(status=Thesis.Status.APPROVED).count(),
			"download_count": Download.objects.count(),
			"top_theses": list(Thesis.objects.filter(is_public=True).order_by("-download_count").values("id", "title", "download_count")[:10]),
			"downloads_by_course": list(Thesis.objects.values("course__name").annotate(total=Count("downloads")).order_by("-total")[:10]),
		}
		return Response(data)
