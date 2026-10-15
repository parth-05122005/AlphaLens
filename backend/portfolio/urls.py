from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter(trailing_slash=True)
router.register("holdings", views.HoldingViewSet, basename="holding")

urlpatterns = [
    path("portfolio/summary/", views.portfolio_summary, name="portfolio-summary"),
    *router.urls,
]
