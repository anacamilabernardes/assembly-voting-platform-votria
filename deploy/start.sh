#!/bin/sh
set -eu
cd /app/backend
python manage.py migrate --noinput
# Idempotent: a restart never deletes existing ballots or audit history.
if [ "${VOTRIA_DEMO_MODE:-false}" = "true" ]; then
    python manage.py seed_demo
fi
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-10000}" --workers 1 --threads 4 --timeout 60 --access-logfile - --error-logfile -
