from rest_framework import serializers

from portfolio.models import Holding

from .models import Agent, AgentRun


class AgentRunSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source="agent.name", read_only=True)

    class Meta:
        model = AgentRun
        fields = [
            "id", "agent", "agent_name", "trigger", "status", "task_id", "output", "citations",
            "error", "created_at", "started_at", "finished_at",
        ]
        read_only_fields = fields


class AgentRunSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentRun
        fields = ["id", "trigger", "status", "created_at", "finished_at"]
        read_only_fields = fields


class AgentSerializer(serializers.ModelSerializer):
    holdings = serializers.PrimaryKeyRelatedField(many=True, queryset=Holding.objects.none(), required=False)
    last_run = serializers.SerializerMethodField()

    class Meta:
        model = Agent
        fields = ["id", "name", "instruction", "holdings", "schedule", "is_active", "created_at", "last_run"]
        read_only_fields = ["created_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None:
            # Only the requesting user's holdings are valid choices.
            self.fields["holdings"].child_relation.queryset = Holding.objects.filter(user=request.user)

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Give the agent a name.")
        return value

    def validate_instruction(self, value):
        value = value.strip()
        if len(value) < 10:
            raise serializers.ValidationError("Describe what the agent should do (at least 10 characters).")
        if len(value) > 2000:
            raise serializers.ValidationError("Keep the instruction under 2000 characters.")
        return value

    def get_last_run(self, obj):
        run = obj.runs.first()  # runs are ordered newest first
        return AgentRunSummarySerializer(run).data if run else None
