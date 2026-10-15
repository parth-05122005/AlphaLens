import io
import time

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from core.locks import redis_lock
from research.ingest import chunk_text, fetch_news, refresh_news_for_holding
from research.models import Chunk, Document

pytestmark = pytest.mark.django_db


def make_pdf(text: str) -> bytes:
    """A one-page PDF whose text pypdf can extract."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data(f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def news_entry(n, title=None):
    return {
        "title": title or f"Infosys headline {n}",
        "link": f"https://news.example.com/{n}",
        "summary": f"<a href='x'>Infosys</a> summary text {n} &amp; more",
        "published_parsed": time.struct_time((2026, 10, 10, 9, 30, 0, 0, 0, 0)),
    }


# --- chunking ---


def test_chunk_text_produces_overlapping_chunks():
    sentences = [f"Sentence number {i} talks about quarterly revenue growth." for i in range(60)]
    text = " ".join(sentences)
    chunks = chunk_text(text, size=300, overlap=60)

    assert len(chunks) > 3
    assert all(len(c) <= 300 for c in chunks)
    for prev, nxt in zip(chunks, chunks[1:]):
        # The start of each chunk repeats the end of the previous one.
        assert nxt[:30] in prev
    # Nothing is lost.
    assert "Sentence number 59" in chunks[-1]


def test_chunk_text_prefers_paragraph_boundaries():
    text = "First paragraph about results.\n\nSecond paragraph about guidance."
    assert chunk_text(text, size=800) == ["First paragraph about results.\n\nSecond paragraph about guidance."]
    assert chunk_text("") == []


# --- PDF upload ---


def test_pdf_upload_creates_document_and_task_makes_it_ready(api, user, make_holding):
    holding = make_holding(user, "INFY.NS")
    pdf = SimpleUploadedFile("Q2 results.pdf", make_pdf("Infosys Q2 revenue grew 5 percent."), "application/pdf")

    resp = api.post("/api/documents/upload/", {"file": pdf, "holding": holding.id}, format="multipart")

    assert resp.status_code == 201, resp.data
    assert resp.data["task_id"]
    assert resp.data["source_type"] == "pdf"
    doc = Document.objects.get(pk=resp.data["id"])
    # Eager Celery already ran the ingest task.
    assert doc.status == Document.Status.READY
    assert doc.holding == holding
    assert "revenue grew" in doc.content
    assert Chunk.objects.filter(document=doc).count() == 1


def test_pdf_upload_rejects_empty_and_non_pdf(api):
    empty = SimpleUploadedFile("blank.pdf", make_pdf(""), "application/pdf")
    resp = api.post("/api/documents/upload/", {"file": empty}, format="multipart")
    assert resp.status_code == 400

    txt = SimpleUploadedFile("notes.txt", b"hello", "text/plain")
    assert api.post("/api/documents/upload/", {"file": txt}, format="multipart").status_code == 400
    assert Document.objects.count() == 0


def test_pdf_upload_rejects_other_users_holding(api, other_user, make_holding):
    theirs = make_holding(other_user, "TCS.NS")
    pdf = SimpleUploadedFile("r.pdf", make_pdf("Some text here."), "application/pdf")
    resp = api.post("/api/documents/upload/", {"file": pdf, "holding": theirs.id}, format="multipart")
    assert resp.status_code == 400


def test_embedding_failure_marks_document_failed(api, mock_llm, monkeypatch):
    def broken(texts, task_type="RETRIEVAL_DOCUMENT"):
        raise ValueError("embedding service exploded")

    monkeypatch.setattr("core.llm.embed_many", broken)
    pdf = SimpleUploadedFile("r.pdf", make_pdf("Some text here."), "application/pdf")

    with pytest.raises(ValueError):  # eager mode propagates task errors
        api.post("/api/documents/upload/", {"file": pdf}, format="multipart")

    doc = Document.objects.get()
    assert doc.status == Document.Status.FAILED
    assert "exploded" in doc.error
    assert doc.chunks.count() == 0


# --- news ---


def test_fetch_news_dedupes_and_strips_html(user, make_holding, mock_feed):
    holding = make_holding(user, "INFY.NS", name="Infosys")
    mock_feed.entries = [news_entry(1), news_entry(2)]

    first = fetch_news(holding)
    assert [d.title for d in first] == ["Infosys headline 1", "Infosys headline 2"]
    assert first[0].content == "Infosys summary text 1 & more"
    assert first[0].published_at is not None
    assert "Infosys+stock" in mock_feed.urls[0] and "gl=IN" in mock_feed.urls[0]

    mock_feed.entries = [news_entry(2), news_entry(3)]
    second = fetch_news(holding)
    assert [d.title for d in second] == ["Infosys headline 3"]
    assert Document.objects.filter(source_type="news").count() == 3


def test_refresh_news_ingests_scores_and_stamps_holding(user, make_holding, mock_feed, mock_llm):
    holding = make_holding(user, "INFY.NS", name="Infosys")
    mock_feed.entries = [news_entry(1, "Infosys wins big deal"), news_entry(2, "Infosys announces layoffs")]

    def scores(prompt):
        return {
            "results": [
                {"id": d.id, "score": 0.7 if "deal" in d.title else -0.8, "label": "positive" if "deal" in d.title else "negative"}
                for d in Document.objects.all()
            ]
        }

    mock_llm.json_reply = scores
    result = refresh_news_for_holding(holding)

    assert result == {"new": 2, "ingested": 2, "scored": 2, "failed": 0}
    assert len(mock_llm.json_calls) == 1  # one batch
    labels = dict(Document.objects.values_list("title", "sentiment_label"))
    assert labels == {"Infosys wins big deal": "positive", "Infosys announces layoffs": "negative"}
    assert Chunk.objects.count() == 2
    holding.refresh_from_db()
    assert holding.news_refreshed_at is not None


def test_refresh_news_skips_when_lock_held(user, make_holding, mock_feed):
    holding = make_holding(user, "INFY.NS")
    mock_feed.entries = [news_entry(1)]

    with redis_lock(f"lock:news:{holding.id}") as acquired:
        assert acquired
        assert refresh_news_for_holding(holding) is None

    assert mock_feed.urls == []  # never even fetched
    assert Document.objects.count() == 0
    assert cache.get(f"lock:news:{holding.id}") is None  # released afterwards
    assert refresh_news_for_holding(holding)["new"] == 1


def test_redis_lock_is_exclusive_and_released():
    with redis_lock("lock:test") as first:
        with redis_lock("lock:test") as second:
            assert first is True and second is False
        assert cache.get("lock:test") == "1"  # the loser must not release the winner's lock
    assert cache.get("lock:test") is None


def test_creating_holding_triggers_news_refresh(api, mock_feed):
    mock_feed.entries = [news_entry(1)]
    resp = api.post("/api/holdings/", {"symbol": "INFY", "quantity": "1", "avg_buy_price": "100"}, format="json")
    assert resp.status_code == 201
    assert Document.objects.filter(holding_id=resp.data["id"], status="ready").count() == 1


def test_refresh_news_endpoint_returns_202(api, user, make_holding, mock_feed):
    holding = make_holding(user, "INFY.NS")
    mock_feed.entries = [news_entry(1)]
    resp = api.post(f"/api/holdings/{holding.id}/refresh-news/")
    assert resp.status_code == 202 and resp.data["task_id"]
    assert api.get(f"/api/documents/?holding={holding.id}&source_type=news").data["count"] == 1


def test_documents_are_user_scoped(api, other_user, make_holding):
    theirs = make_holding(other_user, "TCS.NS")
    doc = Document.objects.create(user=other_user, holding=theirs, source_type="pdf", title="secret", content="x")
    assert api.get("/api/documents/").data["count"] == 0
    assert api.get(f"/api/documents/{doc.id}/").status_code == 404
    assert api.delete(f"/api/documents/{doc.id}/").status_code == 404
