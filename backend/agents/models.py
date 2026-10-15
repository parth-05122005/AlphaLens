from django.conf import settings
from django.db import models


class Agent(models.Model):
    class Schedule(models.TextChoices):
        MANUAL = "manual"
        DAILY = "daily"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agents")
    name = models.CharField(max_length=120)
    instruction = models.TextField()
    # Empty means "all of the user's holdings", resolved at run time.
    holdings = models.ManyToManyField("portfolio.Holding", blank=True, related_name="agents")
    schedule = models.CharField(max_length=10, choices=Schedule.choices, default=Schedule.MANUAL)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class AgentRun(models.Model):
    class Trigger(models.TextChoices):
        MANUAL = "manual"
        SCHEDULED = "scheduled"

    class Status(models.TextChoices):
        QUEUED = "queued"
        RUNNING = "running"
        SUCCESS = "success"
        FAILED = "failed"

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="runs")
    trigger = models.CharField(max_length=10, choices=Trigger.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED)
    task_id = models.CharField(max_length=64, null=True, blank=True)
    output = models.TextField(blank=True)
    citations = models.JSONField(default=list, blank=True)
    error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.agent} #{self.pk} ({self.status})"
