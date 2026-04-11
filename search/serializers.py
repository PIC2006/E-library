from rest_framework import serializers

from theses.serializers import ThesisListSerializer


class SearchSerializer(serializers.Serializer):
    query = serializers.CharField(required=False, allow_blank=True)
    title = serializers.CharField(required=False, allow_blank=True)
    author = serializers.CharField(required=False, allow_blank=True)
    keyword = serializers.CharField(required=False, allow_blank=True)
    course = serializers.CharField(required=False, allow_blank=True)
    year = serializers.IntegerField(required=False)


class SearchResultSerializer(serializers.Serializer):
    thesis = ThesisListSerializer()
    score = serializers.FloatField(required=False)
