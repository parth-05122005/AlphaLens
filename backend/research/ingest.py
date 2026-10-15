"""Turning news headlines and PDFs into embedded chunks."""

import html
import logging
import re
import urllib.request
from datetime import datetime
from datetime import timezone as dt_timezone
from urllib.parse import quote_plus

import feedparser
from django.db import transaction
from django.utils import timezone

from core import llm
from core.locks import redis_lock
from portfolio.services import invalidate_summary, sentiment_label

from .models import Chunk, Document

logger = logging.getLogger(__name__)

SENTIMENT_BATCH = 20
FEED_TIMEOUT = 15


# --- chunking ---


def _split_long(text: str, size: int) -> list[str]:
    """Split a paragraph into sentence-sized pieces no longer than `size`."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    pieces: list[str] = []
    for sentence in sentences:
        while len(sentence) > size:  # a single monster sentence: hard cut
            pieces.append(sentence[:size])
            sentence = sentence[size:]
        if sentence:
            pieces.append(sentence)
    return pieces


def chunk_text(text: str, size: int = 800, overlap: int = 150) -> list[str]:
    """Character-based chunks that prefer paragraph/sentence boundaries.

    Each chunk after the first starts with the last `overlap` characters of the
    previous one so a fact split across a boundary is still retrievable.
    """
    text = re.sub(r"[ \t]+", " ", text or "").strip()
    if not text:
        return []

    units: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if para:
            units.extend(_split_long(para, size - overlap) if len(para) > size - overlap else [para])

    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n\n{unit}" if current else unit
        if len(candidate) <= size:
            current = candidate
            continue
        chunks.append(current)
        tail = current[-overlap:]
        # Start the overlap at a word boundary so chunks don't begin mid-word.
        if " " in tail:
            tail = tail[tail.index(" ") + 1 :]
        current = f"{tail} {unit}".strip()
    if current:
        chunks.append(current)
    return chunks


# --- ingestion ---


def ingest_document(document: Document) -> int:
    """pending -> processing -> chunk + embed -> ready. Marks failed and re-raises on error."""
    document.status = Document.Status.PROCESSING
    document.error = None
    document.save(update_fields=["status", "error"])
    try:
        texts = chunk_text(document.content)
        if not texts:
            raise ValueError("Document has no text to index")
        # Prefix the title so short chunks keep their context in embedding space.
        vectors = llm.embed_many([f"{document.title}\n\n{t}" for t in texts])
        with transaction.atomic():
            document.chunks.all().delete()
            Chunk.objects.bulk_create(
                Chunk(document=document, index=i, text=t, embedding=v) for i, (t, v) in enumerate(zip(texts, vectors))
            )
            document.status = Document.Status.READY
            document.save(update_fields=["status"])
        return len(texts)
    except Exception as exc:
        document.status = Document.Status.FAILED
        document.error = str(exc)[:1000]
        document.save(update_fields=["status", "error"])
        raise


# --- news ---


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def news_feed_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en"


def _fetch_feed(url: str):
    """Download with a timeout (feedparser has none of its own), then parse. Patched in tests."""
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (AlphaLens research bot)"})
    with urllib.request.urlopen(request, timeout=FEED_TIMEOUT) as response:
        return feedparser.parse(response.read())


def _entry_published(entry) -> datetime | None:
    parsed = entry.get("published_parsed")
    if not parsed:
        return None
    return datetime(*parsed[:6], tzinfo=dt_timezone.utc)


def fetch_news(holding, limit: int = 10) -> list[Document]:
    company = holding.name or holding.symbol.split(".")[0]
    feed = _fetch_feed(news_feed_url(f"{company} stock"))
    entries = [e for e in feed.entries[:limit] if e.get("link") and e.get("title")]

    existing = set(
        Document.objects.filter(user=holding.user, url__in=[e["link"] for e in entries]).values_list("url", flat=True)
    )
    created = []
    for entry in entries:
        if entry["link"] in existing:
            continue
        title = strip_html(entry["title"])[:500]
        summary = strip_html(entry.get("summary", ""))
        created.append(
            Document.objects.create(
                user=holding.user,
                holding=holding,
                source_type=Document.SourceType.NEWS,
                title=title,
                url=entry["link"],
                published_at=_entry_published(entry),
                content=summary if summary and summary != title else title,
            )
        )
        existing.add(entry["link"])
    return created


SENTIMENT_SYSTEM = (
    "You are a financial news sentiment classifier for equity investors. "
    "For each headline, judge the likely impact on the company's stock price. "
    'Return JSON: {"results": [{"id": <int>, "score": <float -1..1>, "label": "positive"|"neutral"|"negative"}]}. '
    "Use negative scores for bad news (losses, layoffs, guidance cuts, probes, downgrades), "
    "positive for good news, and near 0 for neutral or mixed news."
)


def score_sentiment(documents) -> int:
    """One generate_json call per batch of up to 20 headlines. Returns how many were scored."""
    documents = list(documents)
    scored = 0
    for start in range(0, len(documents), SENTIMENT_BATCH):
        batch = documents[start : start + SENTIMENT_BATCH]
        by_id = {d.id: d for d in batch}
        lines = "\n".join(f"{d.id}: {d.title}" for d in batch)
        result = llm.generate_json(SENTIMENT_SYSTEM, f"Headlines (id: text):\n{lines}")
        items = result.get("results", []) if isinstance(result, dict) else result
        for item in items or []:
            try:
                doc = by_id[int(item["id"])]
                score = max(-1.0, min(1.0, float(item["score"])))
            except (KeyError, TypeError, ValueError):
                continue
            label = item.get("label")
            doc.sentiment_score = score
            doc.sentiment_label = label if label in Document.Sentiment.values else sentiment_label(score)
            doc.save(update_fields=["sentiment_score", "sentiment_label"])
            scored += 1
    return scored


def refresh_news_for_holding(holding) -> dict | None:
    """Fetch, embed and score news for one holding. Returns None if another worker holds the lock."""
    with redis_lock(f"lock:news:{holding.id}") as acquired:
        if not acquired:
            logger.info("News refresh for %s already running; skipping", holding.symbol)
            return None

        new_docs = fetch_news(holding)

        # Also retry anything left pending/failed by an earlier attempt.
        to_ingest = Document.objects.filter(
            holding=holding,
            source_type=Document.SourceType.NEWS,
            status__in=[Document.Status.PENDING, Document.Status.FAILED],
        )
        errors = []
        ingested = 0
        for doc in to_ingest:
            try:
                ingest_document(doc)
                ingested += 1
            except Exception as exc:
                logger.warning("Ingest failed for document %s: %s", doc.id, exc)
                errors.append(exc)
        if errors and not ingested:
            raise errors[-1]  # likely an outage: let the Celery task retry

        unscored = Document.objects.filter(
            holding=holding,
            source_type=Document.SourceType.NEWS,
            status=Document.Status.READY,
            sentiment_score__isnull=True,
        )
        scored = score_sentiment(unscored)

        holding.news_refreshed_at = timezone.now()
        holding.save(update_fields=["news_refreshed_at"])
        invalidate_summary(holding.user_id)
        return {"new": len(new_docs), "ingested": ingested, "scored": scored, "failed": len(errors)}
