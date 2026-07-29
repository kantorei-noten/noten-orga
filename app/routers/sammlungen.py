"""Sammlungen-Endpunkte (Unter-Bibliotheken)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg.errors import ForeignKeyViolation
from pydantic import BaseModel, Field

from ..auth.deps import current_user, require_role
from ..collections import service
from ..db import get_conn

router = APIRouter(prefix="/sammlungen", tags=["sammlungen"])


# 'art' wird gegen die pflegbare Referenztabelle sammlung_art (FK) geprüft, nicht mehr fest verdrahtet.
class SammlungCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    art: str = Field(default="allgemein", min_length=1, max_length=30)
    notiz: str | None = None


class SammlungUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    art: str | None = Field(default=None, min_length=1, max_length=30)
    notiz: str | None = None


class WerkRef(BaseModel):
    werk_id: UUID


@router.post("", status_code=201)
async def create(data: SammlungCreate, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    try:
        return await service.create_sammlung(conn, data.name, data.art, data.notiz)
    except ForeignKeyViolation:
        raise HTTPException(status_code=400, detail="Unbekannte Sammlungs-Art")


@router.get("")
async def liste(user=Depends(current_user), conn=Depends(get_conn)):
    return await service.list_sammlungen(conn)


@router.get("/{sammlung_id}")
async def detail(sammlung_id: UUID, user=Depends(current_user), conn=Depends(get_conn)):
    s = await service.get_sammlung(conn, sammlung_id)
    if not s:
        raise HTTPException(status_code=404, detail="Sammlung nicht gefunden")
    return s


@router.patch("/{sammlung_id}")
async def update(sammlung_id: UUID, data: SammlungUpdate, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    try:
        s = await service.update_sammlung(conn, sammlung_id, data.model_dump(exclude_unset=True))
    except ForeignKeyViolation:
        raise HTTPException(status_code=400, detail="Unbekannte Sammlungs-Art")
    if not s:
        raise HTTPException(status_code=404, detail="Sammlung nicht gefunden")
    return s


@router.delete("/{sammlung_id}", status_code=204)
async def delete(sammlung_id: UUID, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    if not await service.delete_sammlung(conn, sammlung_id):
        raise HTTPException(status_code=404, detail="Sammlung nicht gefunden")


@router.post("/{sammlung_id}/werke", status_code=204)
async def werk_zuordnen(sammlung_id: UUID, body: WerkRef, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    await service.add_werk(conn, sammlung_id, body.werk_id)


@router.delete("/{sammlung_id}/werke/{werk_id}", status_code=204)
async def werk_entfernen(sammlung_id: UUID, werk_id: UUID, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    if not await service.remove_werk(conn, sammlung_id, werk_id):
        raise HTTPException(status_code=404, detail="Zuordnung nicht gefunden")
