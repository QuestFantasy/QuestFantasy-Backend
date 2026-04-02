#!/bin/sh
set -e

# Validate required environment variables for production
if [ "$ENVIRONMENT" = "production" ]; then
    if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "dev-key-insecure-do-not-use-in-production" ]; then
        echo "[ERROR] SECRET_KEY must be set to a secure value in production"
        exit 1
    fi
    if [ "$DEBUG" = "True" ]; then
        echo "[ERROR] DEBUG must be False in production"
        exit 1
    fi
fi

echo "[web] Waiting for PostgreSQL..."
python - <<'PY'
import os
import time
import psycopg

host = os.getenv("DB_HOST", "db")
port = int(os.getenv("DB_PORT", "5432"))
name = os.getenv("DB_NAME", "questfantasy")
user = os.getenv("DB_USER", "questfantasy")
password = os.getenv("DB_PASSWORD", "questfantasy")

for i in range(30):
    try:
        psycopg.connect(host=host, port=port, dbname=name, user=user, password=password).close()
        print("[web] PostgreSQL is ready")
        break
    except Exception as exc:
        print(f"[web] PostgreSQL not ready ({exc}), retrying...")
        time.sleep(2)
else:
    raise SystemExit("[web] PostgreSQL is unreachable")
PY

echo "[web] Applying migrations..."
python manage.py migrate --noinput

echo "[web] Collecting static files..."
python manage.py collectstatic --noinput --clear

# Calculate optimal number of workers (2 * CPU_CORES + 1)
# Default to 3 for small deployments
WORKERS=${GUNICORN_WORKERS:-$(python -c "import os; print(min(max(2 * os.cpu_count() + 1 if os.cpu_count() else 3, 2), 16))")}

echo "[web] Starting Gunicorn with $WORKERS workers..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "$WORKERS" \
    --worker-class sync \
    --worker-tmp-dir /dev/shm \
    --access-logfile - \
    --error-logfile - \
    --log-level info

