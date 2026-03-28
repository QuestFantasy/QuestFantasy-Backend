#!/bin/sh
set -e

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

echo "[web] Starting Gunicorn..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
