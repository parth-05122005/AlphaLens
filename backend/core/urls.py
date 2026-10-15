from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("tasks/<str:task_id>/", views.task_status, name="task-status"),
]
