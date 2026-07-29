"""Katalog-Endpunkte: Werke, Dubletten, Batch-Bearbeitung, CSV-Import/-Export."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field

from ..auth.deps import current_user, require_role
from ..catalog import service
from ..catalog.models import BatchAnlass, BatchTag, WerkCreate, WerkUpdate
from ..config import get_settings
from ..db import get_conn

router = APIRouter(prefix="/werke", tags=["werke"])


@router.post("", status_code=201)
async def create(data: WerkCreate, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    return await service.create_werk(conn, data)


@router.get("")
async def liste(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user=Depends(current_user),
    conn=Depends(get_conn),
):
    return await service.list_werke(conn, limit, offset)


# --- statische Pfade VOR /{werk_id} ---
@router.get("/baum")
async def baum(
    feld: str = Query("komponist", pattern="^(komponist|gattung|anlass)$"),
    user=Depends(current_user),
    conn=Depends(get_conn),
):
    return await service.werk_baum(conn, feld)


@router.get("/aehnlich")
async def aehnlich(titel: str = Query(min_length=1), user=Depends(current_user), conn=Depends(get_conn)):
    return await service.aehnliche_werke(conn, titel)


@router.get("/export-csv")
async def export_csv(user=Depends(current_user), conn=Depends(get_conn)):
    csv_text = await service.export_csv(conn)
    return Response(
        content="﻿" + csv_text,  # BOM für Excel
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="kantorei-werke.csv"'},
    )


@router.post("/import-csv")
async def import_csv(
    file: UploadFile = File(...), user=Depends(require_role("musiker")), conn=Depends(get_conn)
):
    settings = get_settings()
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Datei zu groß")
    return await service.import_csv(conn, data)


@router.post("/batch/tags")
async def batch_tags(body: BatchTag, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    n = await service.batch_add_tag(conn, body.werk_ids, body.tag)
    return {"gesetzt": n}


@router.post("/batch/anlass")
async def batch_anlass(body: BatchAnlass, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    n = await service.batch_set_anlass(conn, body.werk_ids, body.anlass_id)
    return {"gesetzt": n}


@router.get("/{werk_id}")
async def detail(werk_id: UUID, user=Depends(current_user), conn=Depends(get_conn)):
    werk = await service.get_werk(conn, werk_id)
    if not werk:
        raise HTTPException(status_code=404, detail="Werk nicht gefunden")
    return werk


@router.patch("/{werk_id}")
async def update(werk_id: UUID, data: WerkUpdate, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    werk = await service.update_werk(conn, werk_id, data)
    if not werk:
        raise HTTPException(status_code=404, detail="Werk nicht gefunden")
    return werk


@router.delete("/{werk_id}", status_code=204)
async def delete(werk_id: UUID, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    if not await service.delete_werk(conn, werk_id):
        raise HTTPException(status_code=404, detail="Werk nicht gefunden")


class LiedtextIn(BaseModel):
    text: str | None = Field(default=None, max_length=20000)


@router.post("/{werk_id}/liedtext/extrahieren")
async def liedtext_extrahieren(werk_id: UUID, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    """Liedtext-Vorschlag aus den Notenblättern extrahieren (speichert noch nicht)."""
    if not await service.get_werk(conn, werk_id):
        raise HTTPException(status_code=404, detail="Werk nicht gefunden")
    text = await service.extrahiere_liedtext(conn, werk_id)
    return {"text": text}


@router.put("/{werk_id}/liedtext")
async def liedtext_speichern(werk_id: UUID, body: LiedtextIn, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    werk = await service.set_projektionstext(conn, werk_id, body.text)
    if not werk:
        raise HTTPException(status_code=404, detail="Werk nicht gefunden")
    return werk


@router.post("/{werk_id}/chordpro/erzeugen")
async def chordpro_erzeugen(werk_id: UUID, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    """ChordPro-Vorschlag aus den MusicXML-Noten ableiten (speichert nicht).

    engine ∈ {"music21","basis",""} zeigt, welcher Analyzer den Vorschlag erzeugt hat."""
    if not await service.get_werk(conn, werk_id):
        raise HTTPException(status_code=404, detail="Werk nicht gefunden")
    text, engine = await service.erzeuge_chordpro(conn, werk_id)
    return {"text": text, "engine": engine}
