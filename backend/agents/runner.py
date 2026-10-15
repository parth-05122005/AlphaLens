"""Executes a saved agent: refresh news, gather recent documents, write a cited report."""

import logging
import uuid
from datetime import timedelta

from django.db.models import F
from django.utils import timezone

from core import llm
from portfolio.models import Holding
from research.alerts import recent_news_filter
from research.ingest import refresh_news_for_holding
from research.models import Document
from research.rag import referenced_numbers

from .models import AgentRun

logger = logging.getLogger(__name__)

MAX_SOURCES = 30
SOURCE_CHARS = 600
WINDOW_DAYS = 7

SYSTEM_PROMPT = """You are an AlphaLens research agent working for an Indian retail investor.
Follow the user's instruction using ONLY the numbered sources provided.
Write a short Markdown report: a one-line summary, then bullet points grouped by stock where useful.
Cite every claim with source numbers in square brackets, e.g. [1] or [2][4].
If the sources don't cover something the instruction asks for, say so plainly.
Finish with at most one short line noting this is not investment advice."""


def enqueue_run(run: AgentRun):
    """Queue run_agent_task with a pre-assigned task id, so the id is saved before any worker sees it."""
    from .tasks import run_agent_task

    run.task_id = str(uuid.uuid4())
    run.save(update_fields=["task_id"])
    return run_agent_task.apply_async(args=[run.id], task_id=run.task_id)


def target_holdings(agent) -> list[Holding]:
    selected = list(agent.holdings.all())
    return selected or list(Holding.objects.filter(user=agent.user))


def build_sources(docs) -> str:
    blocks = []
    for n, doc in enumerate(docs, start=1):
        date = (doc.published_at or doc.created_at).date().isoformat()
        kind = "News" if doc.source_type == Document.SourceType.NEWS else "Report"
        symbol = doc.holding.symbol if doc.holding_id else "General"
        blocks.append(f"[{n}] {kind} · {symbol} · {doc.title} ({date})\n{doc.content[:SOURCE_CHARS]}")
    return "\n\n".join(blocks)


def build_citations(output: str, docs) -> list[dict]:
    citations = []
    for n in referenced_numbers(output):
        if 1 <= n <= len(docs):
            doc = docs[n - 1]
            citations.append(
                {
                    "n": n,
                    "document_id": doc.id,
                    "title": doc.title,
                    "url": doc.url,
                    "source_type": doc.source_type,
                    "published_at": doc.published_at.isoformat() if doc.published_at else None,
                    "snippet": doc.content[:200] + ("…" if len(doc.content) > 200 else ""),
                }
            )
    return sorted(citations, key=lambda c: c["n"])


def execute_agent_run(run: AgentRun) -> AgentRun:
    run.status = AgentRun.Status.RUNNING
    run.started_at = timezone.now()
    run.error = None
    run.save(update_fields=["status", "started_at", "error"])
    try:
        agent = run.agent
        holdings = target_holdings(agent)

        for holding in holdings:
            try:
                refresh_news_for_holding(holding)  # same process; respects the per-holding lock
            except Exception:
                logger.warning("News refresh failed for %s during agent run %s", holding.symbol, run.id, exc_info=True)

        since = timezone.now() - timedelta(days=WINDOW_DAYS)
        docs = list(
            Document.objects.filter(user=agent.user, holding__in=holdings, status=Document.Status.READY)
            .filter(recent_news_filter(since))
            .select_related("holding")
            .order_by(F("published_at").desc(nulls_last=True), "-created_at")[:MAX_SOURCES]
        )

        if not docs:
            run.output = (
                "No documents from the last 7 days were found for the selected holdings, so there is nothing to "
                "report yet. Try again after news has been refreshed or a report has been uploaded."
            )
            run.citations = []
        else:
            prompt = f"Instruction: {agent.instruction}\n\nSources:\n\n{build_sources(docs)}"
            run.output = llm.generate(SYSTEM_PROMPT, prompt)
            run.citations = build_citations(run.output, docs)

        run.status = AgentRun.Status.SUCCESS
        run.finished_at = timezone.now()
        run.save(update_fields=["output", "citations", "status", "finished_at"])
        return run
    except Exception as exc:
        run.status = AgentRun.Status.FAILED
        run.error = str(exc)[:1000]
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error", "finished_at"])
        raise
