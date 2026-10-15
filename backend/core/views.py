from celery.result import AsyncResult
from django.core.cache import cache
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from alphalens.celery import app as celery_app


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    db_ok = redis_ok = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_ok = True
    except Exception:
        pass
    try:
        cache.set("health:ping", "1", 5)
        redis_ok = cache.get("health:ping") == "1"
    except Exception:
        pass
    status_code = 200 if db_ok and redis_ok else 503
    return Response(
        {"status": "ok" if status_code == 200 else "degraded", "db": db_ok, "redis": redis_ok},
        status=status_code,
    )


@api_view(["GET"])
def task_status(request, task_id):
    result = AsyncResult(task_id, app=celery_app)
    return Response({"task_id": task_id, "state": result.state, "ready": result.ready()})
