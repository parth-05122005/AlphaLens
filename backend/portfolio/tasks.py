from celery import shared_task
from django.contrib.auth import get_user_model

from core.retry import NETWORK_ERRORS

from .models import Holding
from .services import refresh_prices


@shared_task(autoretry_for=NETWORK_ERRORS, retry_backoff=True, retry_kwargs={"max_retries": 3})
def refresh_prices_task(user_id=None):
    holdings = Holding.objects.all()
    if user_id is not None:
        if not get_user_model().objects.filter(pk=user_id).exists():
            return 0
        holdings = holdings.filter(user_id=user_id)
    return refresh_prices(holdings)
