"""Such-Endpunkt mit Volltext, Fuzzy und Facetten."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ..auth.deps import current_user
from ..db import get_conn
from ..search import suche

router = APIRouter(tags=["suche"])


@router.get("/suche")
async def such_endpunkt(
    q: str | None = Query(None, max_length=200),
    gattung: str | None = None,
    besetzung: str | None = None,
    tonart: str | None = None,
    schwierigkeit: int | None = Query(None, ge=1, le=5),
    sprache: str | None = None,
    rechtestatus: str | None = None,
    anlass_id: UUID | None = None,
    anlass_rekursiv: bool = False,
    tag: str | None = None,
    buch: str | None = None,
    nummer: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user=Depends(current_user),
    conn=Depends(get_conn),
):
    filters = {
        "gattung": gattung,
        "besetzung": besetzung,
        "tonart": tonart,
        "schwierigkeit": schwierigkeit,
        "sprache": sprache,
        "rechtestatus": rechtestatus,
        "anlass_id": str(anlass_id) if anlass_id else None,
        "tag": tag,
        "buch": buch,
        "nummer": nummer,
    }
    return await suche(conn, q, filters, limit, offset, anlass_rekursiv=anlass_rekursiv)
