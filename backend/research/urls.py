from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter(trailing_slash=True)
router.register("documents", views.DocumentViewSet, basename="document")

urlpatterns = [
    path("ask/", views.ask, name="ask"),
    path("ask/history/", views.AskHistoryView.as_view(), name="ask-history"),
    path("stats/", views.stats, name="stats"),
    path("alerts/", views.alerts, name="alerts"),
    *router.urls,
]
