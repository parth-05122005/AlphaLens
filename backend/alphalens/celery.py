import logging
import os

from celery import Celery
from celery.signals import task_postrun, task_prerun

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alphalens.settings")

app = Celery("alphalens")
# Reads CELERY_* settings, including CELERY_BEAT_SCHEDULE.
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

logger = logging.getLogger("alphalens.tasks")


@task_prerun.connect
def log_task_start(task_id=None, task=None, **kwargs):
    logger.info("Task start: %s [%s]", task.name, task_id)


@task_postrun.connect
def log_task_finish(task_id=None, task=None, state=None, **kwargs):
    logger.info("Task finish: %s [%s] state=%s", task.name, task_id, state)


@app.task(bind=True)
def debug_task(self):
    logger.info("debug_task running, request id=%s", self.request.id)
    return "pong"
