from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Agent, AgentRun
from .runner import enqueue_run
from .serializers import AgentRunSerializer, AgentSerializer


class AgentViewSet(viewsets.ModelViewSet):
    serializer_class = AgentSerializer

    def get_queryset(self):
        return Agent.objects.filter(user=self.request.user).prefetch_related("holdings")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        agent = self.get_object()
        run = AgentRun.objects.create(agent=agent, trigger=AgentRun.Trigger.MANUAL, status=AgentRun.Status.QUEUED)
        enqueue_run(run)
        run.refresh_from_db()
        return Response(AgentRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"])
    def runs(self, request, pk=None):
        agent = self.get_object()
        page = self.paginate_queryset(agent.runs.select_related("agent"))
        return self.get_paginated_response(AgentRunSerializer(page, many=True).data)


class AgentRunViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = AgentRunSerializer

    def get_queryset(self):
        return AgentRun.objects.filter(agent__user=self.request.user).select_related("agent")
