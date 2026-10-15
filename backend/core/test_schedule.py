from celery.schedules import crontab
from django.conf import settings

from alphalens.celery import app


def test_beat_schedule_has_the_three_jobs():
    schedule = settings.CELERY_BEAT_SCHEDULE
    tasks = {entry["task"]: entry["schedule"] for entry in schedule.values()}

    assert set(tasks) == {
        "portfolio.tasks.refresh_prices_task",
        "research.tasks.refresh_all_news_task",
        "agents.tasks.run_scheduled_agents_task",
    }
    assert tasks["portfolio.tasks.refresh_prices_task"] == crontab(minute="*/15", hour="9-15", day_of_week="mon-fri")
    assert tasks["research.tasks.refresh_all_news_task"] == crontab(minute=0, hour="*/3")
    assert tasks["agents.tasks.run_scheduled_agents_task"] == crontab(minute=0, hour=8)
    # Celery picked up the schedule and timezone from Django settings.
    assert app.conf.beat_schedule == schedule
    assert app.conf.timezone == "Asia/Kolkata"


def test_scheduled_tasks_are_registered():
    app.loader.import_default_modules()
    for entry in settings.CELERY_BEAT_SCHEDULE.values():
        assert entry["task"] in app.tasks
