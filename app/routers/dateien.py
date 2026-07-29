"""Datei-Endpunkte: Upload (Ingest), Vorschau, Download — alle authentifiziert."""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from ..auth.deps import current_user, require_role
from ..config import get_settings
from ..db import get_conn
from ..ingest.service import ingest_file
from ..ingest.validation import ValidationError
from ..omr.service import extract_musicxml

router = APIRouter(prefix="/dateien", tags=["dateien"])


@router.post("")
async def upload(
    ausgabe_id: UUID = Form(...),
    art: str = Form("scan_pdf"),
    file: UploadFile = File(...),
    user: dict = Depends(require_role("musiker")),
    conn=Depends(get_conn),
):
    settings = get_settings()
    # Größenlimit schon beim Lesen kappen (Speicher-DoS vermeiden)
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Datei zu groß")

    cur = await conn.execute("select 1 from ausgabe where id = %s", (ausgabe_id,))
    if not await cur.fetchone():
        raise HTTPException(status_code=404, detail="Ausgabe nicht gefunden")

    try:
        datei, created = await ingest_file(conn, settings, ausgabe_id, art, file.filename, data)
    except ValidationError as exc:
        raise HTTPException(status_code=415, detail=exc.message)

    return {
        "id": str(datei["id"]),
        "art": datei["art"],
        "sha256": datei["sha256"],
        "mime": datei["mime"],
        "seiten": datei["seiten"],
        "groesse_bytes": datei["groesse_bytes"],
        "hat_vorschau": bool(datei.get("thumb_pfad")),
        "neu": created,
    }


@router.get("/{datei_id}/thumbnail")
async def thumbnail(datei_id: UUID, user: dict = Depends(current_user), conn=Depends(get_conn)):
    cur = await conn.execute("select thumb_pfad from datei where id = %s", (datei_id,))
    row = await cur.fetchone()
    if not row or not row["thumb_pfad"] or not Path(row["thumb_pfad"]).exists():
        raise HTTPException(status_code=404, detail="Keine Vorschau")
    return FileResponse(row["thumb_pfad"], media_type="image/webp")


@router.get("/{datei_id}/musicxml")
async def musicxml(datei_id: UUID, user: dict = Depends(current_user), conn=Depends(get_conn)):
    cur = await conn.execute("select art, pfad from datei where id = %s", (datei_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    if row["art"] != "musicxml":
        raise HTTPException(status_code=415, detail="Keine MusicXML-Datei")
    try:
        # Fremddatei defensiv (defusedxml) in einem Thread parsen — blockiert nicht den Event-Loop
        import anyio

        xml = await anyio.to_thread.run_sync(lambda: extract_musicxml(Path(row["pfad"]).read_bytes()))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message)
    return Response(content=xml, media_type="application/vnd.recordare.musicxml+xml")


@router.get("/{datei_id}/download")
async def download(datei_id: UUID, user: dict = Depends(current_user), conn=Depends(get_conn)):
    cur = await conn.execute(
        "select pfad, mime, original_name from datei where id = %s", (datei_id,)
    )
    row = await cur.fetchone()
    if not row or not Path(row["pfad"]).exists():
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return FileResponse(
        row["pfad"], media_type=row["mime"], filename=row["original_name"] or "datei"
    )


@router.delete("/{datei_id}", status_code=204)
async def loeschen(
    datei_id: UUID,
    user: dict = Depends(require_role("musiker")),
    conn=Depends(get_conn),
):
    cur = await conn.execute(
        "select sha256, pfad, thumb_pfad from datei where id = %s", (datei_id,)
    )
    row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    try:
        await conn.execute("delete from datei where id = %s", (datei_id,))
    except Exception:  # noqa: BLE001 — z. B. FK aus einer Setliste
        raise HTTPException(
            status_code=409,
            detail="Datei wird noch verwendet (z. B. in einer Setliste) und kann nicht gelöscht werden.",
        )
    # Vorschau (pro Datei) entfernen
    if row.get("thumb_pfad"):
        try:
            Path(row["thumb_pfad"]).unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
    # Blob nur löschen, wenn kein anderer Eintrag denselben Inhalt referenziert (Hash-Dedup)
    cur = await conn.execute("select 1 from datei where sha256 = %s limit 1", (row["sha256"],))
    if not await cur.fetchone() and row.get("pfad"):
        try:
            Path(row["pfad"]).unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
