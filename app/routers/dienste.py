"""Gruppen- & Dienstplanungs-Endpunkte."""
from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth.deps import current_user, require_role
from ..db import get_conn
from ..dienste import service

router = APIRouter(tags=["dienste"])


class GruppeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    art: str = Field(default="chor", pattern="^(chor|blaeser|band|sonstige)$")


class MitgliedRef(BaseModel):
    benutzer_id: UUID


class DienstCreate(BaseModel):
    gruppe_id: UUID
    setliste_id: UUID | None = None
    datum: date | None = None
    notiz: str | None = None


class DienstUpdate(BaseModel):
    bestaetigt: bool | None = None
    datum: date | None = None
    setliste_id: UUID | None = None
    notiz: str | None = None


class ZusageIn(BaseModel):
    status: str = Field(pattern="^(zugesagt|abgesagt)$")
    notiz: str | None = None


# --- Gruppen ---
@router.post("/gruppen", status_code=201)
async def gruppe_anlegen(data: GruppeCreate, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    return await service.create_gruppe(conn, data.name, data.art)


@router.get("/gruppen")
async def gruppen(user=Depends(current_user), conn=Depends(get_conn)):
    return await service.list_gruppen(conn)


@router.delete("/gruppen/{gruppe_id}", status_code=204)
async def gruppe_loeschen(gruppe_id: UUID, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    if not await service.delete_gruppe(conn, gruppe_id):
        raise HTTPException(status_code=404, detail="Gruppe nicht gefunden")


@router.post("/gruppen/{gruppe_id}/mitglieder", status_code=204)
async def mitglied_zu(gruppe_id: UUID, body: MitgliedRef, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    await service.add_mitglied(conn, gruppe_id, body.benutzer_id)


@router.delete("/gruppen/{gruppe_id}/mitglieder/{benutzer_id}", status_code=204)
async def mitglied_weg(gruppe_id: UUID, benutzer_id: UUID, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    if not await service.remove_mitglied(conn, gruppe_id, benutzer_id):
        raise HTTPException(status_code=404, detail="Mitgliedschaft nicht gefunden")


# --- Dienste (ganze Gruppe als EIN Dienst) ---
@router.post("/dienste", status_code=201)
async def dienst_planen(data: DienstCreate, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    return await service.create_dienst(conn, data.gruppe_id, data.setliste_id, data.datum, data.notiz)


@router.get("/dienste")
async def dienste(user=Depends(current_user), conn=Depends(get_conn)):
    return await service.list_dienste(conn)


@router.get("/meine-dienste")
async def meine_dienste(user=Depends(current_user), conn=Depends(get_conn)):
    """Dienste, bei denen der angemeldete Nutzer eingetragen ist — inkl. eigener Zusage."""
    return await service.meine_dienste(conn, user["id"])


@router.post("/dienste/{dienst_id}/zusage")
async def zusage(dienst_id: UUID, data: ZusageIn, user=Depends(current_user), conn=Depends(get_conn)):
    """Eigene Teilnahme zu-/absagen (jeder Eingetragene, auch Rolle 'chor')."""
    if not await service.ist_mitglied(conn, dienst_id, user["id"]):
        raise HTTPException(status_code=403, detail="Du bist bei diesem Dienst nicht eingetragen")
    return await service.set_zusage(conn, dienst_id, user["id"], data.status, data.notiz)


@router.patch("/dienste/{dienst_id}")
async def dienst_aendern(dienst_id: UUID, data: DienstUpdate, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    d = await service.update_dienst(conn, dienst_id, data.model_dump(exclude_unset=True))
    if not d:
        raise HTTPException(status_code=404, detail="Dienst nicht gefunden")
    return d


@router.delete("/dienste/{dienst_id}", status_code=204)
async def dienst_loeschen(dienst_id: UUID, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    if not await service.delete_dienst(conn, dienst_id):
        raise HTTPException(status_code=404, detail="Dienst nicht gefunden")
