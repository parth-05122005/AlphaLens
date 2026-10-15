#!/usr/bin/env bash
# Render start command (root directory: backend).
#
# Render's free plan has no background workers, so by default the Celery worker
# and an embedded beat scheduler (-B) run inside this web service. On a paid plan
# set RUN_WORKER_IN_WEB=false and enable the separate worker/beat services in render.yaml.
set -o errexit

if [ "${RUN_WORKER_IN_WEB:-true}" = "true" ]; then
  celery -A alphalens worker -B -l info --concurrency=1 --schedule /tmp/celerybeat-schedule &
fi

# /ask/ waits on the LLM, so allow longer than gunicorn's 30s default.
exec gunicorn alphalens.wsgi:application --workers 2 --bind "0.0.0.0:${PORT:-10000}" --timeout 120
