"""Ingest-Pipeline: validieren → hashen → dedup → speichern → Vorschau."""
from __future__ import annotations

import hashlib

import anyio
from psycopg import AsyncConnection

from ..config import Settings
from . import clamav, storage, thumbnails
from .validation import validate


async def ingest_file(
    conn: AsyncConnection,
    settings: Settings,
    ausgabe_id,
    art_hint: str,
    filename: str | None,
    data: bytes,
) -> tuple[dict, bool]:
    """Nimmt eine Datei an. Rückgabe: (datei-Zeile, neu_angelegt?).

    Wirft ValidationError bei nicht erlaubten/kaputten Dateien.
    """
    # Validierung (inkl. Sandbox-Parsen) in einem Thread — blockiert nicht den Event-Loop
    kind, mime, seiten = await anyio.to_thread.run_sync(validate, data, settings)
    # Optionaler Virenscan (aus per Default; fail-closed wenn konfiguriert)
    await anyio.to_thread.run_sync(clamav.scan, data, settings)
    if kind == "pdf":
        art = art_hint if art_hint in ("scan_pdf", "import_pdf") else "scan_pdf"
    else:
        art = "musicxml"

    sha = hashlib.sha256(data).hexdigest()

    # Dedup: identischer Inhalt bereits an dieser Ausgabe?
    cur = await conn.execute(
        "select * from datei where ausgabe_id = %s and sha256 = %s and art = %s",
        (ausgabe_id, sha, art),
    )
    existing = await cur.fetchone()
    if existing:
        return existing, False

    path = storage.store_blob(settings.data_dir, sha, data)
    safe_name = storage.sanitize_filename(filename)

    cur = await conn.execute(
        """insert into datei (ausgabe_id, art, sha256, pfad, mime, groesse_bytes, seiten, original_name)
           values (%s, %s, %s, %s, %s, %s, %s, %s) returning *""",
        (ausgabe_id, art, sha, str(path), mime, len(data), seiten, safe_name),
    )
    datei = await cur.fetchone()

    if kind == "pdf":
        tp = storage.thumb_path(settings.data_dir, datei["id"])
        try:
            await anyio.to_thread.run_sync(thumbnails.render_pdf_thumbnail, data, tp, settings)
            await conn.execute(
                "update datei set thumb_pfad = %s where id = %s", (str(tp), datei["id"])
            )
            datei["thumb_pfad"] = str(tp)
        except Exception:  # Vorschau ist best-effort, blockiert den Upload nicht
            pass

    return datei, True
