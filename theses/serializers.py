from rest_framework import serializers

from accounts.serializers import UserSerializer
from .models import ApprovalLog, Author, Bookmark, Course, Download, Keyword, Thesis, ThesisPreview


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", "name", "code", "department"]


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ["id", "full_name"]


class KeywordSerializer(serializers.ModelSerializer):
    class Meta:
        model = Keyword
        fields = ["id", "name"]


class ThesisPreviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThesisPreview
        fields = ["id", "page_number", "preview_file", "created_at"]


class ThesisListSerializer(serializers.ModelSerializer):
    authors = AuthorSerializer(many=True, read_only=True)
    keywords = KeywordSerializer(many=True, read_only=True)
    course = CourseSerializer(read_only=True)
    uploaded_by = UserSerializer(read_only=True)

    class Meta:
        model = Thesis
        fields = [
            "id",
            "title",
            "abstract",
            "pdf_file",
            "course",
            "year",
            "authors",
            "keywords",
            "status",
            "is_public",
            "download_count",
            "uploaded_by",
            "created_at",
            "published_at",
        ]


class ThesisDetailSerializer(ThesisListSerializer):
    approval_logs = serializers.SerializerMethodField()
    bookmarked = serializers.SerializerMethodField()
    previews = ThesisPreviewSerializer(many=True, read_only=True)

    class Meta(ThesisListSerializer.Meta):
        fields = ThesisListSerializer.Meta.fields + ["approval_logs", "bookmarked", "search_document", "previews"]

    def get_approval_logs(self, obj):
        return [
            {"action": log.action, "note": log.note, "created_at": log.created_at.isoformat()}
            for log in obj.approval_logs.select_related("admin")
        ]

    def get_bookmarked(self, obj):
        user = self.context["request"].user
        if not user.is_authenticated:
            return False
        return Bookmark.objects.filter(user=user, thesis=obj).exists()


class ThesisWriteSerializer(serializers.ModelSerializer):
    author_names = serializers.ListField(child=serializers.CharField(), write_only=True)
    keyword_names = serializers.ListField(child=serializers.CharField(), required=False, write_only=True)

    class Meta:
        model = Thesis
        fields = [
            "title",
            "abstract",
            "pdf_file",
            "course",
            "year",
            "preview_page",
            "author_names",
            "keyword_names",
        ]

    def create(self, validated_data):
        author_names = validated_data.pop("author_names", [])
        keyword_names = validated_data.pop("keyword_names", [])
        request = self.context["request"]
        thesis = Thesis.objects.create(uploaded_by=request.user, status=Thesis.Status.PENDING, **validated_data)
        thesis.authors.set([Author.objects.get_or_create(full_name=name.strip())[0] for name in author_names if name.strip()])
        thesis.keywords.set([Keyword.objects.get_or_create(name=name.strip().lower())[0] for name in keyword_names if name.strip()])
        return thesis

    def update(self, instance, validated_data):
        author_names = validated_data.pop("author_names", None)
        keyword_names = validated_data.pop("keyword_names", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if author_names is not None:
            instance.authors.set([Author.objects.get_or_create(full_name=name.strip())[0] for name in author_names if name.strip()])
        if keyword_names is not None:
            instance.keywords.set([Keyword.objects.get_or_create(name=name.strip().lower())[0] for name in keyword_names if name.strip()])
        return instance


class BookmarkSerializer(serializers.ModelSerializer):
    thesis = ThesisListSerializer(read_only=True)

    class Meta:
        model = Bookmark
        fields = ["id", "thesis", "created_at"]


class DownloadSerializer(serializers.ModelSerializer):
    thesis = serializers.PrimaryKeyRelatedField(read_only=True)
    user = UserSerializer(read_only=True)

    class Meta:
        model = Download
        fields = ["id", "thesis", "user", "ip_address", "user_agent", "created_at"]


class ApprovalLogSerializer(serializers.ModelSerializer):
    admin = UserSerializer(read_only=True)

    class Meta:
        model = ApprovalLog
        fields = ["id", "action", "note", "admin", "created_at"]
