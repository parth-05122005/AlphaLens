import pytest
from django.urls import reverse

from alphalens.celery import debug_task


@pytest.mark.django_db
def test_health_reports_db_and_cache(client):
    resp = client.get(reverse("health"))
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "db": True, "redis": True}


def test_debug_task_runs_eagerly():
    assert debug_task.delay().get() == "pong"
