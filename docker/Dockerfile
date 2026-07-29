# App-Image: FastAPI + uvicorn. Schlank — enthält bewusst KEIN music21 (das lebt im Worker).
FROM python:3.13-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

# Abhängigkeiten zuerst (eigene Cache-Ebene) — reproduzierbar aus uv.lock
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# App-Code
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

FROM python:3.13-slim AS runtime
ENV PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
# Nicht-Root-Benutzer
RUN useradd -u 10001 -r -s /usr/sbin/nologin noten \
    && mkdir -p /data && chown noten:noten /data
WORKDIR /app
COPY --from=build --chown=noten:noten /app /app
COPY --chown=noten:noten docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV NOTEN_DATA_DIR=/data NOTEN_ENVIRONMENT=prod
USER noten
EXPOSE 8001
# Migrationen anwenden, dann API starten (nur an das interne Compose-Netz binden)
ENTRYPOINT ["/entrypoint.sh"]
CMD ["api"]
