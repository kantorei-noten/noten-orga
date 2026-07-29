"""Referenzdaten & Autovervollständigung für die Erfassungs-UI — inkl. Pflege (Einstellungen)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg.errors import ForeignKeyViolation, UniqueViolation
from pydantic import BaseModel, Field

from ..auth.deps import current_user, require_role
from ..db import get_conn

router = APIRouter(tags=["refs"])


# ---------------- Lesen (alle angemeldeten Nutzer) ----------------
@router.get("/anlaesse")
async def anlaesse(user=Depends(current_user), conn=Depends(get_conn)):
    cur = await conn.execute(
        "select id, name, parent_id, sortierung from anlass order by sortierung, name"
    )
    return await cur.fetchall()


@router.get("/besetzungen")
async def besetzungen(user=Depends(current_user), conn=Depends(get_conn)):
    cur = await conn.execute("select kuerzel, name, sortierung from besetzung order by sortierung, kuerzel")
    return await cur.fetchall()


@router.get("/sammlung-arten")
async def sammlung_arten(user=Depends(current_user), conn=Depends(get_conn)):
    cur = await conn.execute("select kuerzel, name, sortierung from sammlung_art order by sortierung, kuerzel")
    return await cur.fetchall()


@router.get("/gesangbuecher")
async def gesangbuecher(user=Depends(current_user), conn=Depends(get_conn)):
    cur = await conn.execute("select kuerzel, name from gesangbuch order by sortierung")
    return await cur.fetchall()


@router.get("/tags")
async def tags(q: str = Query("", max_length=100), user=Depends(current_user), conn=Depends(get_conn)):
    cur = await conn.execute(
        "select name from tag where name ilike %s order by name limit 15", (q + "%",)
    )
    return [r["name"] for r in await cur.fetchall()]


@router.get("/komponisten")
async def komponisten(q: str = Query("", max_length=100), user=Depends(current_user), conn=Depends(get_conn)):
    cur = await conn.execute(
        "select distinct komponist from werk where komponist ilike %s "
        "order by komponist limit 15",
        (q + "%",),
    )
    return [r["komponist"] for r in await cur.fetchall()]


# ---------------- Pflegen (Rolle musiker) ----------------
class KuerzelIn(BaseModel):
    kuerzel: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=100)
    sortierung: int = 0


class KuerzelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sortierung: int | None = None


class AnlassIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    sortierung: int = 0
    parent_id: UUID | None = None


class AnlassUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sortierung: int | None = None


async def _patch(conn, tabelle: str, spalte: str, key, fields: dict) -> dict | None:
    fields = {k: v for k, v in fields.items() if k in ("name", "sortierung") and v is not None}
    if fields:
        sets = ", ".join(f"{k} = %s" for k in fields)
        await conn.execute(
            f"update {tabelle} set {sets} where {spalte} = %s", (*fields.values(), key)
        )
    cur = await conn.execute(f"select * from {tabelle} where {spalte} = %s", (key,))
    return await cur.fetchone()


# --- Besetzungen ---
@router.post("/besetzungen", status_code=201)
async def besetzung_anlegen(data: KuerzelIn, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    try:
        cur = await conn.execute(
            "insert into besetzung (kuerzel, name, sortierung) values (%s,%s,%s) returning *",
            (data.kuerzel, data.name, data.sortierung),
        )
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="Kürzel existiert bereits")
    return await cur.fetchone()


@router.patch("/besetzungen/{kuerzel}")
async def besetzung_aendern(kuerzel: str, data: KuerzelUpdate, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    row = await _patch(conn, "besetzung", "kuerzel", kuerzel, data.model_dump(exclude_unset=True))
    if not row:
        raise HTTPException(status_code=404, detail="Besetzung nicht gefunden")
    return row


@router.delete("/besetzungen/{kuerzel}", status_code=204)
async def besetzung_loeschen(kuerzel: str, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    try:
        cur = await conn.execute("delete from besetzung where kuerzel = %s", (kuerzel,))
    except ForeignKeyViolation:
        raise HTTPException(status_code=409, detail="Besetzung wird von Werken verwendet und kann nicht gelöscht werden")
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Besetzung nicht gefunden")


# --- Sammlungs-Arten ---
@router.post("/sammlung-arten", status_code=201)
async def art_anlegen(data: KuerzelIn, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    try:
        cur = await conn.execute(
            "insert into sammlung_art (kuerzel, name, sortierung) values (%s,%s,%s) returning *",
            (data.kuerzel, data.name, data.sortierung),
        )
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="Kürzel existiert bereits")
    return await cur.fetchone()


@router.patch("/sammlung-arten/{kuerzel}")
async def art_aendern(kuerzel: str, data: KuerzelUpdate, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    row = await _patch(conn, "sammlung_art", "kuerzel", kuerzel, data.model_dump(exclude_unset=True))
    if not row:
        raise HTTPException(status_code=404, detail="Art nicht gefunden")
    return row


@router.delete("/sammlung-arten/{kuerzel}", status_code=204)
async def art_loeschen(kuerzel: str, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    try:
        cur = await conn.execute("delete from sammlung_art where kuerzel = %s", (kuerzel,))
    except ForeignKeyViolation:
        raise HTTPException(status_code=409, detail="Art wird von Sammlungen verwendet und kann nicht gelöscht werden")
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Art nicht gefunden")


# --- Anlässe / Kirchenjahr ---
@router.post("/anlaesse", status_code=201)
async def anlass_anlegen(data: AnlassIn, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    cur = await conn.execute(
        "insert into anlass (name, sortierung, parent_id) values (%s,%s,%s) returning *",
        (data.name, data.sortierung, data.parent_id),
    )
    return await cur.fetchone()


@router.patch("/anlaesse/{anlass_id}")
async def anlass_aendern(anlass_id: UUID, data: AnlassUpdate, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    row = await _patch(conn, "anlass", "id", anlass_id, data.model_dump(exclude_unset=True))
    if not row:
        raise HTTPException(status_code=404, detail="Anlass nicht gefunden")
    return row


@router.delete("/anlaesse/{anlass_id}", status_code=204)
async def anlass_loeschen(anlass_id: UUID, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    cur = await conn.execute("delete from anlass where id = %s", (anlass_id,))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Anlass nicht gefunden")
