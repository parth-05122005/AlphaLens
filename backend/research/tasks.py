from celery import group, shared_task

from core.retry import NETWORK_ERRORS
from portfolio.models import Holding

from .ingest import ingest_document, refresh_news_for_holding
from .models import Document


@shared_task(autoretry_for=NETWORK_ERRORS, retry_backoff=True, retry_kwargs={"max_retries": 3})
def refresh_news_for_holding_task(holding_id):
    holding = Holding.objects.filter(pk=holding_id).first()
    if holding is None:
        return None
    return refresh_news_for_holding(holding)


@shared_task
def refresh_all_news_task():
    """Beat job: fan out one refresh task per holding so they run in parallel across workers."""
    holding_ids = list(Holding.objects.values_list("id", flat=True))
    if holding_ids:
        group(refresh_news_for_holding_task.s(holding_id) for holding_id in holding_ids).apply_async()
    return len(holding_ids)


@shared_task(autoretry_for=NETWORK_ERRORS, retry_backoff=True, retry_kwargs={"max_retries": 3})
def ingest_document_task(document_id):
    document = Document.objects.filter(pk=document_id).first()
    if document is None:
        return None
    return ingest_document(document)
