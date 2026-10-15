import pytest
from django.core.management import call_command
from django.utils import timezone

from agents.models import Agent, AgentRun
from agents.runner import execute_agent_run
from agents.tasks import run_scheduled_agents_task
from research.models import Document

pytestmark = pytest.mark.django_db


def ready_news(user, holding, title):
    return Document.objects.create(
        user=user,
        holding=holding,
        source_type="news",
        title=title,
        url=f"https://news.example.com/{title.replace(' ', '-')}",
        content=f"{title}. More detail here.",
        status="ready",
        published_at=timezone.now(),
    )


@pytest.fixture
def agent(user, make_holding):
    infy = make_holding(user, "INFY.NS")
    a = Agent.objects.create(user=user, name="IT watch", instruction="Summarize news for my IT stocks and flag layoffs.")
    a.holdings.add(infy)
    return a


def test_create_agent_validates_holdings_belong_to_user(api, user, other_user, make_holding):
    mine = make_holding(user, "INFY.NS")
    theirs = make_holding(other_user, "TCS.NS")
    payload = {"name": "Daily brief", "instruction": "Summarize everything important.", "schedule": "daily"}

    resp = api.post("/api/agents/", {**payload, "holdings": [theirs.id]}, format="json")
    assert resp.status_code == 400

    resp = api.post("/api/agents/", {**payload, "holdings": [mine.id]}, format="json")
    assert resp.status_code == 201
    assert resp.data["holdings"] == [mine.id] and resp.data["schedule"] == "daily"
    assert resp.data["last_run"] is None


def test_agents_are_user_scoped(api, other_user):
    theirs = Agent.objects.create(user=other_user, name="x", instruction="Some long instruction")
    assert api.get("/api/agents/").data["count"] == 0
    assert api.post(f"/api/agents/{theirs.id}/run/").status_code == 404


def test_run_endpoint_returns_202_and_run_succeeds(api, user, agent, mock_llm):
    ready_news(user, agent.holdings.first(), "Infosys announces layoffs")
    mock_llm.generate_reply = "**Summary**: layoffs announced [1]."

    resp = api.post(f"/api/agents/{agent.id}/run/")

    assert resp.status_code == 202
    assert resp.data["trigger"] == "manual" and resp.data["task_id"]
    run = AgentRun.objects.get(pk=resp.data["id"])
    assert run.task_id == resp.data["task_id"]
    assert run.status == AgentRun.Status.SUCCESS  # eager Celery already ran it
    assert run.output.startswith("**Summary**")
    assert [c["title"] for c in run.citations] == ["Infosys announces layoffs"]
    assert run.started_at and run.finished_at

    polled = api.get(f"/api/agent-runs/{run.id}/").data
    assert polled["status"] == "success"
    assert api.get(f"/api/agents/{agent.id}/runs/").data["count"] == 1
    assert api.get(f"/api/agents/{agent.id}/").data["last_run"]["status"] == "success"
    # The instruction and numbered sources reached the model.
    _, prompt = mock_llm.generate_calls[0]
    assert "Instruction: Summarize news for my IT stocks" in prompt and "[1] News · INFY.NS" in prompt


def test_llm_error_marks_run_failed(user, agent, mock_llm):
    ready_news(user, agent.holdings.first(), "Infosys news")
    mock_llm.generate_reply = RuntimeError("model overloaded")
    run = AgentRun.objects.create(agent=agent, trigger="manual")

    with pytest.raises(RuntimeError):
        execute_agent_run(run)

    run.refresh_from_db()
    assert run.status == AgentRun.Status.FAILED
    assert "overloaded" in run.error
    assert run.finished_at is not None


def test_agent_with_no_holdings_uses_all_and_handles_no_documents(user, make_holding, mock_llm):
    make_holding(user, "INFY.NS")
    a = Agent.objects.create(user=user, name="All", instruction="Summarize everything important.")
    run = execute_agent_run(AgentRun.objects.create(agent=a, trigger="manual"))
    assert run.status == AgentRun.Status.SUCCESS
    assert "No documents" in run.output
    assert mock_llm.generate_calls == []


def test_scheduled_task_only_queues_active_daily_agents(user, mock_llm):
    daily = Agent.objects.create(user=user, name="Daily", instruction="Daily brief please.", schedule="daily")
    Agent.objects.create(user=user, name="Manual", instruction="Manual brief please.", schedule="manual")
    Agent.objects.create(user=user, name="Paused", instruction="Paused brief please.", schedule="daily", is_active=False)

    assert run_scheduled_agents_task.delay().get() == 1

    runs = AgentRun.objects.all()
    assert [(r.agent_id, r.trigger) for r in runs] == [(daily.id, "scheduled")]
    assert runs[0].task_id


def test_run_agents_command(user):
    Agent.objects.create(user=user, name="Daily", instruction="Daily brief please.", schedule="daily")
    call_command("run_agents")
    assert AgentRun.objects.filter(trigger="scheduled").count() == 1
