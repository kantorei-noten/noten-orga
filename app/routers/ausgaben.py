"""Ausgabe-Endpunkte: Rechtestatus setzen (einzeln + in Masse).

Das Copyright-Gate (app/print/service.py) lässt nur 'public_domain'/'lizenziert' bündeln.
Beim Import bleiben Ausgaben auf 'unbekannt' → hiermit korrigierbar.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth.deps import require_role
from ..db import get_conn

router = APIRouter(prefix="/ausgaben", tags=["ausgaben"])

_RECHTE = "^(public_domain|lizenziert|unbekannt|gesperrt)$"


class RechteIn(BaseModel):
    rechtestatus: str = Field(pattern=_RECHTE)


class RechteMasse(BaseModel):
    von: str = Field(pattern=_RECHTE)
    auf: str = Field(pattern=_RECHTE)


@router.post("/rechtestatus-masse")
async def rechte_masse(data: RechteMasse, user=Depends(require_role("admin")), conn=Depends(get_conn)):
    """Alle Ausgaben mit Status `von` auf `auf` setzen (Admin; z. B. importierten PD-Bestand freigeben)."""
    cur = await conn.execute(
        "update ausgabe set rechtestatus = %s where rechtestatus = %s", (data.auf, data.von)
    )
    return {"geaendert": cur.rowcount}


@router.patch("/{ausgabe_id}")
async def rechte_setzen(ausgabe_id: UUID, data: RechteIn, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    cur = await conn.execute(
        "update ausgabe set rechtestatus = %s where id = %s returning id, rechtestatus",
        (data.rechtestatus, ausgabe_id),
    )
    row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Ausgabe nicht gefunden")
    return row
