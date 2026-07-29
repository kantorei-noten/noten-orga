"""Druck-Endpunkte: druckfertige Sammel-PDFs (Rolle musiker+)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from ..auth.deps import require_role
from ..db import get_conn
from ..print import service
from ..print.service import CopyrightError

router = APIRouter(prefix="/druck", tags=["druck"])


def _pdf(data: bytes, filename: str) -> Response:
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/setliste/{setliste_id}")
async def setliste(
    setliste_id: UUID,
    a4: bool = False,
    bundsteg_mm: int = 0,
    user=Depends(require_role("musiker")),
    conn=Depends(get_conn),
):
    try:
        data = await service.setlist_pdf(conn, setliste_id, a4=a4, bundsteg_mm=bundsteg_mm)
    except CopyrightError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if data is None:
        raise HTTPException(status_code=404, detail="Keine druckbaren Noten in der Setliste")
    return _pdf(data, "setliste.pdf")


@router.get("/ausgabe/{ausgabe_id}/stimmen")
async def stimmen(ausgabe_id: UUID, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    try:
        data = await service.stimmen_batch_pdf(conn, ausgabe_id)
    except CopyrightError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if data is None:
        raise HTTPException(status_code=404, detail="Keine Stimmen definiert")
    return _pdf(data, "stimmen.pdf")


@router.get("/stimme/{stimme_id}")
async def stimme(stimme_id: UUID, user=Depends(require_role("musiker")), conn=Depends(get_conn)):
    try:
        data = await service.einzelstimme_pdf(conn, stimme_id)
    except CopyrightError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if data is None:
        raise HTTPException(status_code=404, detail="Stimme nicht gefunden")
    return _pdf(data, "stimme.pdf")
