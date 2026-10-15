from rest_framework import serializers

from .models import Document


class DocumentSerializer(serializers.ModelSerializer):
    holding_symbol = serializers.CharField(source="holding.symbol", default=None, read_only=True)
    snippet = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id", "holding", "holding_symbol", "source_type", "title", "url", "published_at",
            "status", "error", "sentiment_score", "sentiment_label", "created_at", "snippet",
        ]
        read_only_fields = fields

    def get_snippet(self, obj):
        text = obj.content or ""
        return text[:240] + ("…" if len(text) > 240 else "")


class DocumentDetailSerializer(DocumentSerializer):
    class Meta(DocumentSerializer.Meta):
        fields = [*DocumentSerializer.Meta.fields, "content"]
        read_only_fields = fields
