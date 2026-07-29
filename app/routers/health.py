"""Health-/Readiness-Endpunkt mit DB-Prüfung."""
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict:
    """Öffentliche Readiness-Probe — bewusst OHNE Versions-/Fehlerdetails (kein Fingerprinting)."""
    db = "down"
    try:
        async with request.app.state.pool.connection() as conn:
            await conn.execute("select 1")
            db = "ok"
    except Exception:  # noqa: BLE001 — Health soll nie werfen
        db = "down"
    return {"status": "ok" if db == "ok" else "degraded", "db": db}
