"""Benutzerverwaltung (nur Admin) — kein Self-Signup: Konten legt der Admin an."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, Field

from ..auth import service
from ..auth.deps import require_role
from ..db import get_conn

router = APIRouter(prefix="/benutzer", tags=["benutzer"])


class BenutzerCreate(BaseModel):
    benutzername: str = Field(min_length=1, max_length=100)
    passwort: str = Field(min_length=8, max_length=200)
    rolle: str = Field(default="chor", pattern="^(admin|musiker|chor|gast)$")
    email: str | None = None


class BenutzerUpdate(BaseModel):
    rolle: str | None = Field(default=None, pattern="^(admin|musiker|chor|gast)$")
    aktiv: bool | None = None
    benutzername: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=200)


class PasswortSetzen(BaseModel):
    passwort: str = Field(min_length=8, max_length=200)


class ZfaSetzen(BaseModel):
    aktiv: bool


@router.post("", status_code=201)
async def anlegen(data: BenutzerCreate, user=Depends(require_role("admin")), conn=Depends(get_conn)):
    try:
        row = await service.create_user(conn, data.benutzername, data.passwort, data.rolle, data.email)
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="Benutzername existiert bereits")
    return {
        "id": str(row["id"]),
        "benutzername": row["benutzername"],
        "rolle": row["rolle"],
        "totp_secret": row["totp_secret"],
        "totp_uri": row["totp_uri"],
    }


@router.get("")
async def liste(user=Depends(require_role("admin")), conn=Depends(get_conn)):
    return await service.list_users(conn)


@router.get("/auswahl")
async def auswahl(user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    """Nur id + Benutzername (aktive Konten) — für Mitglieder-/Zuweisungs-Picker."""
    return await service.list_user_namen(conn)


@router.patch("/{benutzer_id}")
async def aendern(benutzer_id: UUID, data: BenutzerUpdate, user=Depends(require_role("admin")), conn=Depends(get_conn)):
    target = await service.get_user(conn, benutzer_id)
    if not target:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    fields = data.model_dump(exclude_unset=True)
    # Aussperr-Schutz: den letzten aktiven Admin nicht herabstufen/deaktivieren
    entzieht_admin = (fields.get("rolle") not in (None, "admin")) or (fields.get("aktiv") is False)
    if entzieht_admin and target["rolle"] == "admin" and target["aktiv"]:
        if await service.count_active_admins(conn) <= 1:
            raise HTTPException(status_code=400, detail="Der letzte aktive Admin kann nicht deaktiviert/herabgestuft werden.")
    try:
        row = await service.set_user(conn, benutzer_id, fields)
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="Benutzername oder E-Mail existiert bereits")
    if not row:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    return row


@router.post("/{benutzer_id}/passwort", status_code=204)
async def passwort_setzen(benutzer_id: UUID, data: PasswortSetzen, user=Depends(require_role("admin")), conn=Depends(get_conn)):
    if not await service.admin_set_password(conn, benutzer_id, data.passwort):
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")


@router.post("/{benutzer_id}/2fa")
async def zwei_fa(benutzer_id: UUID, data: ZfaSetzen, user=Depends(require_role("admin")), conn=Depends(get_conn)):
    row = await service.set_2fa(conn, benutzer_id, data.aktiv)
    if not row:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    return row


@router.delete("/{benutzer_id}", status_code=204)
async def loeschen(benutzer_id: UUID, user=Depends(require_role("admin")), conn=Depends(get_conn)):
    if str(benutzer_id) == str(user["id"]):
        raise HTTPException(status_code=400, detail="Sich selbst kann man nicht löschen.")
    target = await service.get_user(conn, benutzer_id)
    if not target:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    if target["rolle"] == "admin" and target["aktiv"] and await service.count_active_admins(conn) <= 1:
        raise HTTPException(status_code=400, detail="Der letzte aktive Admin kann nicht gelöscht werden.")
    await service.delete_user(conn, benutzer_id)
