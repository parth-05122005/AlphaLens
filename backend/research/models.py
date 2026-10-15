from django.conf import settings
from django.db import models
from pgvector.django import HnswIndex, VectorField


class Document(models.Model):
    class SourceType(models.TextChoices):
        NEWS = "news"
        PDF = "pdf"

    class Status(models.TextChoices):
        PENDING = "pending"
        PROCESSING = "processing"
        READY = "ready"
        FAILED = "failed"

    class Sentiment(models.TextChoices):
        POSITIVE = "positive"
        NEUTRAL = "neutral"
        NEGATIVE = "negative"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="documents")
    holding = models.ForeignKey(
        "portfolio.Holding", on_delete=models.CASCADE, null=True, blank=True, related_name="documents"
    )
    source_type = models.CharField(max_length=10, choices=SourceType.choices)
    title = models.CharField(max_length=500)
    url = models.URLField(max_length=2000, null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    content = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    error = models.TextField(null=True, blank=True)
    sentiment_score = models.FloatField(null=True, blank=True)
    sentiment_label = models.CharField(max_length=10, choices=Sentiment.choices, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = [models.F("published_at").desc(nulls_last=True), "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "url"],
                condition=models.Q(source_type="news"),
                name="unique_news_url_per_user",
            )
        ]

    def __str__(self):
        return self.title


class Chunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    index = models.PositiveIntegerField()
    text = models.TextField()
    embedding = VectorField(dimensions=settings.EMBEDDING_DIM)

    class Meta:
        ordering = ["document_id", "index"]
        indexes = [
            HnswIndex(
                name="chunk_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            )
        ]
