"""FastAPI-Anwendung (App-Factory + Lifespan)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .db import make_pool
from .logging import setup_logging
from .routers import (
    annotationen,
    ausgaben,
    auth,
    backup,
    benutzer,
    chordpro,
    dateien,
    dienste,
    druck,
    health,
    jobs,
    refs,
    sammlungen,
    setlisten,
    stimmen,
    suche,
    werke,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.pool = make_pool(settings.database_url)
    await app.state.pool.open(wait=True)
    try:
        yield
    finally:
        await app.state.pool.close()


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)
    # OpenAPI-Docs nur in der Entwicklung — in Prod kein Schema/Playground exponieren
    _dev = settings.environment == "dev"
    app = FastAPI(
        title="Kantorei — Notenarchiv",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if _dev else None,
        redoc_url="/redoc" if _dev else None,
        openapi_url="/openapi.json" if _dev else None,
    )
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(dateien.router, prefix="/api")
    app.include_router(werke.router, prefix="/api")
    app.include_router(refs.router, prefix="/api")
    app.include_router(suche.router, prefix="/api")
    app.include_router(setlisten.router, prefix="/api")
    app.include_router(druck.router, prefix="/api")
    app.include_router(annotationen.router, prefix="/api")
    app.include_router(ausgaben.router, prefix="/api")
    app.include_router(sammlungen.router, prefix="/api")
    app.include_router(stimmen.router, prefix="/api")
    app.include_router(dienste.router, prefix="/api")
    app.include_router(chordpro.router, prefix="/api")
    app.include_router(benutzer.router, prefix="/api")
    app.include_router(backup.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    return app


app = create_app()
