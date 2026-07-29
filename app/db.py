"""Datenbank-Zugriff über einen asynchronen psycopg3-Connection-Pool."""
from __future__ import annotations

from typing import AsyncIterator

from fastapi import Request
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


def make_pool(url: str) -> AsyncConnectionPool:
    """Erzeugt den Pool (noch geschlossen — Öffnen erfolgt im Lifespan)."""
    return AsyncConnectionPool(
        conninfo=url,
        min_size=1,
        max_size=10,
        open=False,
        kwargs={"autocommit": True, "row_factory": dict_row},
    )


async def get_conn(request: Request) -> AsyncIterator[AsyncConnection]:
    """FastAPI-Dependency: eine Verbindung aus dem Pool je Request."""
    async with request.app.state.pool.connection() as conn:
        yield conn
