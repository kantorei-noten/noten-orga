#!/usr/bin/env bash
# Lokaler, isolierter Postgres-Cluster für Entwicklung & Tests.
# Port 5433 (rührt eine vorhandene Postgres.app auf 5432 nicht an).
# Idempotent: initdb bei Bedarf, Start, Rollen/DBs anlegen.
set -euo pipefail

# Postgres.app-Binaries finden (Fallback: PATH)
for cand in \
  "/Applications/Postgres.app/Contents/Versions/latest/bin" \
  "/opt/homebrew/opt/postgresql@18/bin" \
  "/opt/homebrew/bin"; do
  [ -x "$cand/pg_ctl" ] && export PATH="$cand:$PATH" && break
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PGDATA="$ROOT/.devdb"
PORT="${NOTEN_PGPORT:-5433}"
SOCK="/tmp"
LOG="$PGDATA/server.log"

if [ ! -s "$PGDATA/PG_VERSION" ]; then
  echo "initdb → $PGDATA"
  initdb -D "$PGDATA" -U postgres --auth=trust --encoding=UTF8 >/dev/null
fi

if ! pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
  echo "starte Postgres (Port $PORT)"
  pg_ctl -D "$PGDATA" -l "$LOG" -o "-p $PORT -k $SOCK" -w start
else
  echo "Postgres läuft bereits"
fi

psql -h "$SOCK" -p "$PORT" -U postgres -v ON_ERROR_STOP=1 <<'SQL'
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'noten_app') THEN
    CREATE ROLE noten_app LOGIN PASSWORD 'devpw';
  END IF;
END $$;
SELECT 'CREATE DATABASE noten OWNER noten_app'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'noten')\gexec
SELECT 'CREATE DATABASE noten_test OWNER noten_app'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'noten_test')\gexec
SQL

echo "OK · Datenbanken 'noten' und 'noten_test' bereit auf localhost:${PORT} (Rolle noten_app / devpw)"
echo "Stoppen: pg_ctl -D \"$PGDATA\" stop"
