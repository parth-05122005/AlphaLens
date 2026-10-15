from django.contrib import admin

from .models import Agent, AgentRun


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "schedule", "is_active", "created_at")
    list_filter = ("schedule", "is_active")


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ("agent", "trigger", "status", "created_at", "finished_at")
    list_filter = ("status", "trigger")
