"""Annotations-Endpunkte (eigene Ebenen/Overlays; Objekt-ACL fail-closed)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..annotations import service
from ..auth.deps import current_user, require_role
from ..db import get_conn

router = APIRouter(prefix="/ausgaben", tags=["annotationen"])


class AnnotationIn(BaseModel):
    ebene: str = Field(default="notiz", min_length=1, max_length=50)
    seite: int = Field(default=1, ge=1)
    daten: dict = {}
    geteilt: bool = False


@router.get("/{ausgabe_id}/annotationen/geteilt")
async def geteilte_ebenen(
    ausgabe_id: UUID,
    seite: int = Query(1, ge=1),
    user=Depends(current_user),
    conn=Depends(get_conn),
):
    return await service.list_geteilt(conn, ausgabe_id, seite)


@router.get("/{ausgabe_id}/annotationen/seiten")
async def seiten_mit_notizen(
    ausgabe_id: UUID,
    user=Depends(current_user),
    conn=Depends(get_conn),
):
    """Seiten mit eigenen Notizen — für den 'Mit Notizen'-Button."""
    return {"seiten": await service.seiten_mit_inhalt(conn, ausgabe_id, user["id"])}


@router.get("/{ausgabe_id}/annotationen")
async def liste(
    ausgabe_id: UUID,
    seite: int = Query(1, ge=1),
    user=Depends(current_user),
    conn=Depends(get_conn),
):
    return await service.list_for_page(conn, ausgabe_id, user["id"], seite)


@router.put("/{ausgabe_id}/annotationen")
async def speichern(
    ausgabe_id: UUID,
    body: AnnotationIn,
    user=Depends(require_role("musiker")),
    conn=Depends(get_conn),
):
    return await service.upsert(
        conn, ausgabe_id, user["id"], body.ebene, body.seite, body.daten, body.geteilt
    )


@router.delete("/{ausgabe_id}/annotationen/{ann_id}", status_code=204)
async def loeschen(
    ausgabe_id: UUID,
    ann_id: UUID,
    user=Depends(require_role("musiker")),
    conn=Depends(get_conn),
):
    if not await service.delete(conn, ann_id, user["id"]):
        raise HTTPException(status_code=404, detail="Annotation nicht gefunden")
