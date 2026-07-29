#!/usr/bin/env bash
# Migriert eine lokale DB auf den neuesten Stand. Argument: DB-Name (default: noten).
set -euo pipefail
cd "$(dirname "$0")/.."
DB="${1:-noten}"
export NOTEN_DATABASE_URL="postgresql://noten_app:devpw@localhost:5433/${DB}"
echo "Migriere ${DB} → head"
uv run alembic upgrade head
