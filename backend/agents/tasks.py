from celery import shared_task

from core.retry import NETWORK_ERRORS

from .models import Agent, AgentRun
from .runner import enqueue_run, execute_agent_run


@shared_task(autoretry_for=NETWORK_ERRORS, retry_backoff=True, retry_kwargs={"max_retries": 3})
def run_agent_task(run_id):
    run = AgentRun.objects.select_related("agent").filter(pk=run_id).first()
    if run is None:
        return None
    execute_agent_run(run)
    return run.status


@shared_task
def run_scheduled_agents_task():
    queued = 0
    for agent in Agent.objects.filter(is_active=True, schedule=Agent.Schedule.DAILY):
        run = AgentRun.objects.create(agent=agent, trigger=AgentRun.Trigger.SCHEDULED, status=AgentRun.Status.QUEUED)
        enqueue_run(run)
        queued += 1
    return queued
