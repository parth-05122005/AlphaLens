from django.contrib import admin

from .models import Chunk, Document, QueryLog


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "holding", "source_type", "status", "sentiment_label", "published_at")
    list_filter = ("source_type", "status", "sentiment_label")
    search_fields = ("title", "user__username")


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ("document", "index")
    exclude = ("embedding",)


@admin.register(QueryLog)
class QueryLogAdmin(admin.ModelAdmin):
    list_display = ("question", "user", "cache_hit", "latency_ms", "created_at")
    list_filter = ("cache_hit",)
    exclude = ("question_embedding",)
