#!/usr/bin/env bash
# Render start command (root directory: backend).
#
# Render's free plan has no background workers, so by default the Celery worker
# and an embedded beat scheduler (-B) run inside this web service. On a paid plan
# set RUN_WORKER_IN_WEB=false and enable the separate worker/beat services in render.yaml.
#
# The free plan caps memory at 512 MB, so everything here is kept to as few
# Python processes as possible: a solo-pool worker (no forked child) and
# gunicorn sized by WEB_CONCURRENCY, which Render sets to 1.
set -o errexit

# Free plan has no Shell tab, so the demo account can be seeded on boot instead.
# It runs before the worker starts so the two never hold memory at the same time.
seed() {
  if [ "${SEED_DEMO_ON_START:-false}" = "true" ]; then
    python manage.py seed_demo || echo "seed_demo failed; the app still runs"
  fi
}

if [ "${RUN_WORKER_IN_WEB:-true}" = "true" ]; then
  (seed; exec celery -A alphalens worker -B -l info --pool=solo --schedule /tmp/celerybeat-schedule) &
else
  seed &
fi

# /ask/ waits on the LLM, so allow longer than gunicorn's 30s default.
exec gunicorn alphalens.wsgi:application --workers "${WEB_CONCURRENCY:-2}" --bind "0.0.0.0:${PORT:-10000}" --timeout 120
