"""Druck-Bündelung: Einzelstimmen, Setlist-PDF, SATB-Batch — mit Copyright-Gate.

Rechtlich fail-closed: gebündelt/weitergegeben wird nur, was nachweislich
gemeinfrei oder lizenziert ist. Default 'unbekannt' = gesperrt.
"""
from __future__ import annotations

from pathlib import Path

import pymupdf
from psycopg import AsyncConnection

from ..setlists.service import get_setliste

ERLAUBTE_RECHTE = {"public_domain", "lizenziert"}


class CopyrightError(Exception):
    """Bündeln/Weitergabe rechtlich nicht erlaubt."""


async def _pruefe_rechte(conn: AsyncConnection, ausgabe_ids: set) -> None:
    ids = [i for i in ausgabe_ids if i]
    if not ids:
        return
    cur = await conn.execute(
        "select rechtestatus from ausgabe where id = any(%s)", (ids,)
    )
    for row in await cur.fetchall():
        if row["rechtestatus"] not in ERLAUBTE_RECHTE:
            raise CopyrightError(
                "Bündeln/Weitergabe gesperrt: mindestens eine Ausgabe ist nicht "
                "gemeinfrei oder lizenziert (Rechtestatus prüfen)."
            )


def _append(out: pymupdf.Document, data: bytes, von: int | None, bis: int | None) -> int:
    """Hängt einen Seitenbereich an und gibt die 1-basierte Startseite zurück."""
    src = pymupdf.open(stream=data, filetype="pdf")
    try:
        fp = (von - 1) if von else 0
        tp = (bis - 1) if bis else src.page_count - 1
        fp = max(0, min(fp, src.page_count - 1))
        tp = max(fp, min(tp, src.page_count - 1))
        start = out.page_count + 1
        out.insert_pdf(src, from_page=fp, to_page=tp)
        return start
    finally:
        src.close()


def _to_a4(doc: pymupdf.Document, bundsteg_mm: int = 0) -> pymupdf.Document:
    """Legt jede Seite proportional (ohne Beschnitt) auf A4; optional Bundsteg links."""
    a4 = pymupdf.paper_rect("a4")
    bund = bundsteg_mm * 72 / 25.4
    out = pymupdf.open()
    for i in range(doc.page_count):
        page = out.new_page(width=a4.width, height=a4.height)
        target = pymupdf.Rect(10 + bund, 10, a4.width - 10, a4.height - 10)
        page.show_pdf_page(target, doc, i, keep_proportion=True)
    return out


def extract_pages(data: bytes, von: int | None = None, bis: int | None = None) -> bytes:
    out = pymupdf.open()
    try:
        _append(out, data, von, bis)
        return out.tobytes()
    finally:
        out.close()


async def einzelstimme_pdf(conn: AsyncConnection, stimme_id) -> bytes | None:
    cur = await conn.execute(
        """select st.seite_von, st.seite_bis, d.pfad, d.ausgabe_id
           from stimme st join datei d on d.id = st.datei_id where st.id = %s""",
        (stimme_id,),
    )
    row = await cur.fetchone()
    if not row:
        return None
    await _pruefe_rechte(conn, {row["ausgabe_id"]})
    data = Path(row["pfad"]).read_bytes()
    return extract_pages(data, row["seite_von"], row["seite_bis"])


async def stimmen_batch_pdf(conn: AsyncConnection, ausgabe_id) -> bytes | None:
    cur = await conn.execute(
        """select st.name, st.seite_von, st.seite_bis, d.pfad
           from stimme st join datei d on d.id = st.datei_id
           where d.ausgabe_id = %s order by st.sortierung, st.name""",
        (ausgabe_id,),
    )
    stimmen = await cur.fetchall()
    if not stimmen:
        return None
    await _pruefe_rechte(conn, {ausgabe_id})
    out = pymupdf.open()
    toc = []
    try:
        for st in stimmen:
            start = _append(out, Path(st["pfad"]).read_bytes(), st["seite_von"], st["seite_bis"])
            toc.append([1, st["name"], start])
        out.set_toc(toc)
        return out.tobytes()
    finally:
        out.close()


async def setlist_pdf(
    conn: AsyncConnection, setliste_id, a4: bool = False, bundsteg_mm: int = 0
) -> bytes | None:
    s = await get_setliste(conn, setliste_id)
    if not s:
        return None
    entries = [e for e in s["eintraege"] if e.get("datei_id")]
    if not entries:
        return None
    ausgabe_ids = {(e.get("aufgeloeste_ausgabe_id") or e.get("ausgabe_id")) for e in entries}
    await _pruefe_rechte(conn, ausgabe_ids)  # fail-closed VOR dem Bündeln

    out = pymupdf.open()
    toc = []
    for e in entries:
        cur = await conn.execute("select pfad from datei where id = %s", (e["datei_id"],))
        row = await cur.fetchone()
        if not row:
            continue
        start = _append(out, Path(row["pfad"]).read_bytes(), e.get("seite_von"), e.get("seite_bis"))
        toc.append([1, e.get("werk_titel") or e.get("titel") or "Titel", start])
    if out.page_count == 0:
        out.close()
        return None
    final = _to_a4(out, bundsteg_mm) if a4 else out
    if final is not out:
        out.close()
    final.set_toc(toc)  # Bookmarks bleiben (1:1-Seitenzuordnung)
    data = final.tobytes()
    final.close()
    return data
