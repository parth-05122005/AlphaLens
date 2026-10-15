from celery import shared_task

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


@shared_task(autoretry_for=NETWORK_ERRORS, retry_backoff=True, retry_kwargs={"max_retries": 3})
def ingest_document_task(document_id):
    document = Document.objects.filter(pk=document_id).first()
    if document is None:
        return None
    return ingest_document(document)
