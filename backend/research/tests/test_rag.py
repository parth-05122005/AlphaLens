import pytest
from django.test import override_settings

from conftest import fake_vector
from research.models import Chunk, Document, QueryLog
from research.rag import NO_DOCUMENTS_ANSWER, answer_question, build_citations, referenced_numbers, retrieve

pytestmark = pytest.mark.django_db


def add_doc(user, text, holding=None, status="ready", title=None, source_type="news"):
    doc = Document.objects.create(
        user=user,
        holding=holding,
        source_type=source_type,
        title=title or text[:40],
        url=f"https://example.com/{Document.objects.count()}" if source_type == "news" else None,
        content=text,
        status=status,
    )
    Chunk.objects.create(document=doc, index=0, text=text, embedding=fake_vector(text))
    return doc


def test_retrieval_only_returns_current_users_ready_chunks(user, other_user):
    mine = add_doc(user, "Infosys quarterly revenue beat estimates")
    add_doc(user, "Infosys revenue pending processing", status="processing")
    add_doc(other_user, "Infosys revenue for someone else")

    chunks = retrieve(user, fake_vector("Infosys revenue"))

    assert [c.document_id for c in chunks] == [mine.id]


def test_retrieval_respects_holding_filter(user, make_holding):
    infy = make_holding(user, "INFY.NS")
    tcs = make_holding(user, "TCS.NS")
    add_doc(user, "Infosys revenue grew", holding=infy)
    tcs_doc = add_doc(user, "TCS revenue grew", holding=tcs)

    chunks = retrieve(user, fake_vector("revenue grew"), holding_ids=[tcs.id])
    assert [c.document_id for c in chunks] == [tcs_doc.id]


def test_answer_returns_only_referenced_citations(api, user, mock_llm):
    first = add_doc(user, "Infosys raised its full year revenue guidance", title="Infosys raises guidance")
    add_doc(user, "Infosys signs a large deal with a European bank", title="Infosys bank deal")
    mock_llm.generate_reply = "Infosys raised guidance [1]. Not advice."

    resp = api.post("/api/ask/", {"question": "Did Infosys raise revenue guidance?"}, format="json")

    assert resp.status_code == 200, resp.data
    assert resp.data["cache_hit"] is False
    assert resp.data["answer"].startswith("Infosys raised guidance [1]")
    assert len(resp.data["citations"]) == 1
    citation = resp.data["citations"][0]
    assert citation["n"] == 1 and citation["document_id"] == first.id
    assert set(citation) == {"n", "document_id", "title", "url", "source_type", "published_at", "snippet"}
    # Sources were numbered in the prompt.
    _, prompt = mock_llm.generate_calls[0]
    assert "[1] News" in prompt and "Question: Did Infosys raise revenue guidance?" in prompt


def test_near_identical_question_is_a_cache_hit_without_generate(api, user, mock_llm):
    add_doc(user, "Infosys raised its full year revenue guidance")
    mock_llm.generate_reply = "Yes, guidance was raised [1]."

    first = api.post("/api/ask/", {"question": "Did Infosys raise its revenue guidance?"}, format="json").data
    second = api.post("/api/ask/", {"question": "did infosys raise its revenue guidance"}, format="json").data

    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert second["answer"] == first["answer"]
    assert second["citations"] == first["citations"]
    assert len(mock_llm.generate_calls) == 1
    assert list(QueryLog.objects.order_by("created_at").values_list("cache_hit", flat=True)) == [False, True]


def test_different_question_or_holding_filter_is_not_cached(api, user, make_holding, mock_llm):
    infy = make_holding(user, "INFY.NS")
    add_doc(user, "Infosys raised its full year revenue guidance", holding=infy)
    q = "Did Infosys raise its revenue guidance?"

    api.post("/api/ask/", {"question": q}, format="json")
    filtered = api.post("/api/ask/", {"question": q, "holding_ids": [infy.id]}, format="json").data
    different = api.post("/api/ask/", {"question": "What are the layoff plans at TCS this quarter?"}, format="json").data

    assert filtered["cache_hit"] is False
    assert different["cache_hit"] is False
    assert len(mock_llm.generate_calls) == 3


def test_no_documents_returns_friendly_message_without_llm(api, mock_llm):
    resp = api.post("/api/ask/", {"question": "How is my portfolio doing?"}, format="json")
    assert resp.data["answer"] == NO_DOCUMENTS_ANSWER
    assert resp.data["citations"] == []
    assert mock_llm.generate_calls == []


def test_ask_validation(api, other_user, make_holding):
    assert api.post("/api/ask/", {"question": "hi"}, format="json").status_code == 400
    assert api.post("/api/ask/", {"question": "x" * 501}, format="json").status_code == 400
    theirs = make_holding(other_user, "TCS.NS")
    resp = api.post("/api/ask/", {"question": "What about TCS?", "holding_ids": [theirs.id]}, format="json")
    assert resp.status_code == 400


@override_settings(ASK_RATE_LIMIT="2/minute")
def test_ask_is_rate_limited(api):
    for _ in range(2):
        assert api.post("/api/ask/", {"question": "Anything new?"}, format="json").status_code == 200
    resp = api.post("/api/ask/", {"question": "Anything new?"}, format="json")
    assert resp.status_code == 429


def test_history_and_stats(api, user, mock_llm):
    add_doc(user, "Infosys raised its full year revenue guidance")
    q = {"question": "Did Infosys raise its revenue guidance?"}
    api.post("/api/ask/", q, format="json")
    api.post("/api/ask/", q, format="json")

    history = api.get("/api/ask/history/").data
    assert history["count"] == 2
    assert history["results"][0]["cache_hit"] is True  # newest first

    stats = api.get("/api/stats/").data
    assert stats["total_queries"] == 2
    assert stats["cache_hit_rate"] == 0.5
    assert stats["avg_latency_ms_cached"] is not None
    assert stats["avg_latency_ms_uncached"] is not None
    assert stats["documents_count"] == 1 and stats["chunks_count"] == 1


def test_citation_parsing_handles_groups_and_invented_numbers(user):
    assert referenced_numbers("A [2], B [1, 3] and [2] again") == [2, 1, 3]
    doc = add_doc(user, "Only one source")
    chunk = Chunk.objects.select_related("document").get(document=doc)
    assert [c["n"] for c in build_citations("See [1] and [7]", [chunk])] == [1]


def test_answer_question_service_logs_latency(user, mock_llm):
    add_doc(user, "Reliance retail expansion plans")
    result = answer_question(user, "What are Reliance retail expansion plans?")
    log = QueryLog.objects.get()
    assert log.latency_ms == result["latency_ms"] >= 0
    assert log.holding_ids == []
