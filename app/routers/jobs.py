"""Hintergrund-Jobs: anstoßen + Fortschritt abfragen (Admin).

Die App legt nur Job-Zeilen an; die eigentliche Arbeit (Import, music21-Analyse) macht der
Worker-Container, der die Tabelle `job` abarbeitet und Fortschritt zurückschreibt. Das
Frontend pollt GET /jobs/{id} für den Fortschrittsbalken.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth.deps import require_role
from ..db import get_conn

router = APIRouter(prefix="/jobs", tags=["jobs"])

# Erlaubte Job-Typen (der Worker kennt die Handler). Whitelist gegen beliebige Typen.
JOB_TYPEN = {"chordpro_music21", "import_bach", "import_mutopia", "import_cpdl"}


class JobCreate(BaseModel):
    typ: str = Field(min_length=1, max_length=50)
    params: dict = Field(default_factory=dict)


@router.post("", status_code=201)
async def anlegen(data: JobCreate, user=Depends(require_role("admin")), conn=Depends(get_conn)):
    if data.typ not in JOB_TYPEN:
        raise HTTPException(status_code=400, detail=f"Unbekannter Job-Typ (erlaubt: {', '.join(sorted(JOB_TYPEN))})")
    # nicht denselben Typ doppelt laufen lassen
    cur = await conn.execute(
        "select 1 from job where typ = %s and status in ('offen','laeuft') limit 1", (data.typ,)
    )
    if await cur.fetchone():
        raise HTTPException(status_code=409, detail="Dieser Job läuft bereits")
    import json

    cur = await conn.execute(
        "insert into job (typ, params) values (%s, %s) returning *", (data.typ, json.dumps(data.params))
    )
    return await cur.fetchone()


@router.get("")
async def liste(user=Depends(require_role("admin")), conn=Depends(get_conn)):
    cur = await conn.execute("select * from job order by created_at desc limit 20")
    return await cur.fetchall()


@router.get("/{job_id}")
async def status(job_id: UUID, user=Depends(require_role("admin")), conn=Depends(get_conn)):
    cur = await conn.execute("select * from job where id = %s", (job_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    return row


@router.post("/{job_id}/abbrechen", status_code=204)
async def abbrechen(job_id: UUID, user=Depends(require_role("admin")), conn=Depends(get_conn)):
    await conn.execute(
        "update job set status = 'abgebrochen', updated_at = now() where id = %s and status in ('offen','laeuft')",
        (job_id,),
    )
