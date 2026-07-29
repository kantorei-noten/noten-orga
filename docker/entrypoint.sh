#!/usr/bin/env bash
# Startet je nach Argument den API-Server oder den Worker. Beim API-Start werden zuerst
# die DB-Migrationen angewendet (idempotent).
set -euo pipefail

case "${1:-api}" in
  api)
    echo "[entrypoint] alembic upgrade head …"
    python -m alembic upgrade head
    echo "[entrypoint] uvicorn (0.0.0.0:8001, nur internes Netz) …"
    exec uvicorn app.main:app --host 0.0.0.0 --port 8001
    ;;
  worker)
    echo "[entrypoint] Worker-Loop …"
    exec python -m worker.main
    ;;
  *)
    exec "$@"
    ;;
esac
