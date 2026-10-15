from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter(trailing_slash=True)
router.register("agents", views.AgentViewSet, basename="agent")
router.register("agent-runs", views.AgentRunViewSet, basename="agent-run")

urlpatterns = [*router.urls]
