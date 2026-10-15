"""Retrieval-augmented answers with a pgvector-backed semantic cache. Synchronous: the user is waiting."""

import re
import time
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from pgvector.django import CosineDistance

from core import llm

from .models import Chunk, Document, QueryLog

TOP_K = 8
SNIPPET_CHARS = 200

NO_DOCUMENTS_ANSWER = (
    "I don't have any documents about that yet. Try refreshing news or uploading a report."
)

SYSTEM_PROMPT = """You are AlphaLens, a research assistant for an Indian retail investor's stock portfolio.
Rules:
- Answer ONLY from the numbered sources provided. Do not use outside knowledge.
- Cite every claim with the source number in square brackets, e.g. [1] or [2][3].
- If the sources don't contain the answer, say so clearly instead of guessing.
- Be concise: a short paragraph or a few bullet points, in Markdown.
- End with at most one short line noting this is not investment advice."""

CITATION_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def _since():
    return timezone.now() - timedelta(hours=settings.SEMANTIC_CACHE_TTL_HOURS)


def find_cached(user, embedding, holding_ids):
    """Most similar recent answered question with the same holding filter, if similar enough."""
    match = (
        QueryLog.objects.filter(user=user, cache_hit=False, created_at__gte=_since(), holding_ids=holding_ids)
        .exclude(citations=[])  # never replay "no sources" answers; new documents may exist now
        .annotate(distance=CosineDistance("question_embedding", embedding))
        .order_by("distance")
        .first()
    )
    if match is not None and 1 - match.distance >= settings.SEMANTIC_CACHE_THRESHOLD:
        return match
    return None


def retrieve(user, embedding, holding_ids=None, k=TOP_K):
    qs = Chunk.objects.filter(document__user=user, document__status=Document.Status.READY)
    if holding_ids:
        qs = qs.filter(document__holding_id__in=holding_ids)
    return list(
        qs.select_related("document").annotate(distance=CosineDistance("embedding", embedding)).order_by("distance")[:k]
    )


def build_prompt(question, chunks) -> str:
    blocks = []
    for n, chunk in enumerate(chunks, start=1):
        doc = chunk.document
        date = (doc.published_at or doc.created_at).date().isoformat()
        kind = "News" if doc.source_type == Document.SourceType.NEWS else "Report"
        holding = f" · {doc.holding.symbol}" if doc.holding_id else ""
        blocks.append(f"[{n}] {kind}{holding} · {doc.title} ({date})\n{chunk.text}")
    sources = "\n\n".join(blocks)
    return f"Sources:\n\n{sources}\n\nQuestion: {question}"


def referenced_numbers(answer: str) -> list[int]:
    seen: list[int] = []
    for group in CITATION_RE.findall(answer):
        for part in group.split(","):
            n = int(part)
            if n not in seen:
                seen.append(n)
    return seen


def build_citations(answer, chunks) -> list[dict]:
    citations = []
    for n in referenced_numbers(answer):
        if not 1 <= n <= len(chunks):
            continue  # the model invented a source number
        chunk = chunks[n - 1]
        doc = chunk.document
        snippet = chunk.text[:SNIPPET_CHARS] + ("…" if len(chunk.text) > SNIPPET_CHARS else "")
        citations.append(
            {
                "n": n,
                "document_id": doc.id,
                "title": doc.title,
                "url": doc.url,
                "source_type": doc.source_type,
                "published_at": doc.published_at.isoformat() if doc.published_at else None,
                "snippet": snippet,
            }
        )
    return sorted(citations, key=lambda c: c["n"])


def answer_question(user, question: str, holding_ids=None) -> dict:
    start = time.perf_counter()
    holding_ids = sorted(set(holding_ids or []))
    embedding = llm.embed(question)

    def finish(answer, citations, cache_hit):
        latency_ms = int((time.perf_counter() - start) * 1000)
        QueryLog.objects.create(
            user=user,
            question=question,
            question_embedding=embedding,
            holding_ids=holding_ids,
            answer=answer,
            citations=citations,
            cache_hit=cache_hit,
            latency_ms=latency_ms,
        )
        return {"answer": answer, "citations": citations, "cache_hit": cache_hit, "latency_ms": latency_ms}

    cached = find_cached(user, embedding, holding_ids)
    if cached is not None:
        return finish(cached.answer, cached.citations, cache_hit=True)

    chunks = retrieve(user, embedding, holding_ids)
    if not chunks:
        return finish(NO_DOCUMENTS_ANSWER, [], cache_hit=False)

    answer = llm.generate(SYSTEM_PROMPT, build_prompt(question, chunks))
    return finish(answer, build_citations(answer, chunks), cache_hit=False)
