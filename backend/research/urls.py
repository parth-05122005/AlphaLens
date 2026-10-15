from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter(trailing_slash=True)
router.register("documents", views.DocumentViewSet, basename="document")

urlpatterns = [*router.urls]
