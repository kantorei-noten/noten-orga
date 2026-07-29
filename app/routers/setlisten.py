"""Setlisten-Endpunkte (Gottesdienstablauf)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ..auth.deps import current_user, require_role
from ..db import get_conn
from ..setlists import service
from ..setlists.models import (
    EintragCreate,
    EintragUpdate,
    Reihenfolge,
    SetlisteCreate,
    SetlisteUpdate,
)

router = APIRouter(prefix="/setlisten", tags=["setlisten"])


@router.post("", status_code=201)
async def create(data: SetlisteCreate, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    return await service.create_setliste(conn, data)


@router.get("")
async def liste(user=Depends(current_user), conn=Depends(get_conn)):
    return await service.list_setlisten(conn)


@router.get("/{setliste_id}")
async def detail(setliste_id: UUID, user=Depends(current_user), conn=Depends(get_conn)):
    s = await service.get_setliste(conn, setliste_id)
    if not s:
        raise HTTPException(status_code=404, detail="Setliste nicht gefunden")
    return s


@router.patch("/{setliste_id}")
async def update(setliste_id: UUID, data: SetlisteUpdate, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    s = await service.update_setliste(conn, setliste_id, data)
    if not s:
        raise HTTPException(status_code=404, detail="Setliste nicht gefunden")
    return s


@router.delete("/{setliste_id}", status_code=204)
async def delete(setliste_id: UUID, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    if not await service.delete_setliste(conn, setliste_id):
        raise HTTPException(status_code=404, detail="Setliste nicht gefunden")


@router.post("/{setliste_id}/eintraege", status_code=201)
async def add_eintrag(setliste_id: UUID, data: EintragCreate, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    e = await service.add_eintrag(conn, setliste_id, data)
    if e is None:
        raise HTTPException(status_code=404, detail="Setliste nicht gefunden")
    return e


@router.patch("/{setliste_id}/eintraege/{eintrag_id}")
async def update_eintrag(setliste_id: UUID, eintrag_id: UUID, data: EintragUpdate, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    e = await service.update_eintrag(conn, setliste_id, eintrag_id, data)
    if e is None:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    return e


@router.delete("/{setliste_id}/eintraege/{eintrag_id}", status_code=204)
async def remove_eintrag(setliste_id: UUID, eintrag_id: UUID, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    if not await service.remove_eintrag(conn, setliste_id, eintrag_id):
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")


@router.put("/{setliste_id}/reihenfolge")
async def reihenfolge(setliste_id: UUID, body: Reihenfolge, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    s = await service.reorder(conn, setliste_id, body.eintrag_ids)
    if not s:
        raise HTTPException(status_code=404, detail="Setliste nicht gefunden")
    return s
