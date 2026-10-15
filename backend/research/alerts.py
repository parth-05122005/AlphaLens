"""Risk alerts computed on request from recent news sentiment (no table needed)."""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from portfolio.models import Holding

from .models import Document

WINDOW_DAYS = 7
AVG_THRESHOLD = -0.3
NEGATIVE_COUNT_THRESHOLD = 2


def recent_news_filter(since) -> Q:
    """News published since `since`; undated items count by when we stored them."""
    return Q(published_at__gte=since) | Q(published_at__isnull=True, created_at__gte=since)


def get_alerts(user) -> list[dict]:
    since = timezone.now() - timedelta(days=WINDOW_DAYS)
    news = (
        Document.objects.filter(user=user, source_type=Document.SourceType.NEWS, sentiment_score__isnull=False)
        .filter(recent_news_filter(since))
        .only("id", "holding_id", "title", "url", "published_at", "sentiment_score", "sentiment_label")
    )
    by_holding: dict[int, list[Document]] = {}
    for doc in news:
        if doc.holding_id:
            by_holding.setdefault(doc.holding_id, []).append(doc)

    alerts = []
    for holding in Holding.objects.filter(user=user, id__in=by_holding.keys()):
        docs = by_holding[holding.id]
        avg = sum(d.sentiment_score for d in docs) / len(docs)
        negatives = sorted(
            (d for d in docs if d.sentiment_label == Document.Sentiment.NEGATIVE), key=lambda d: d.sentiment_score
        )
        reasons = []
        if avg < AVG_THRESHOLD:
            reasons.append(f"average news sentiment is {avg:.2f} over the last {WINDOW_DAYS} days")
        if len(negatives) >= NEGATIVE_COUNT_THRESHOLD:
            reasons.append(f"{len(negatives)} negative headlines in the last {WINDOW_DAYS} days")
        if not reasons:
            continue
        alerts.append(
            {
                "holding_id": holding.id,
                "symbol": holding.symbol,
                "name": holding.name,
                "average_sentiment": round(avg, 2),
                "reason": "; ".join(reasons).capitalize(),
                "headlines": [
                    {
                        "document_id": d.id,
                        "title": d.title,
                        "url": d.url,
                        "published_at": d.published_at.isoformat() if d.published_at else None,
                        "sentiment_score": d.sentiment_score,
                    }
                    for d in negatives[:3]
                ],
            }
        )
    return sorted(alerts, key=lambda a: a["average_sentiment"])
