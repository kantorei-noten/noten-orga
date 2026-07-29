"""Externe Import-Jobs (Mutopia …) als Worker-Handler.

Wiederverwendung: die Crawl-/Parse-/Mapping-Funktionen der vorhandenen scripts/import_*.py,
aber statt über die HTTP-API zu gehen, schreiben wir über die **App-Services**
(catalog.create_werk + ingest.ingest_file) — so sind die Importe identisch zu manuellen
Uploads (Magic-Byte-Validierung, Sandbox-Parsen, Thumbnail, sha256-Dedup). Weil die Services
async sind, läuft der Import in einem eigenen asyncio-Loop; der Fortschritt geht über die
synchrone Worker-Verbindung (ctx).
"""
from __future__ import annotations

import asyncio
import os


def import_mutopia(conn, job, ctx):
    """Sync-Entry (vom Worker aufgerufen): crawlt Mutopia und importiert die A4-PDFs."""
    params = job.get("params") or {}
    scope = params.get("scope", "all")
    limit = int(params.get("limit", 0) or 0)
    asyncio.run(_mutopia(ctx, scope, limit))


async def _mutopia(ctx, scope: str, limit: int) -> None:
    import psycopg
    from psycopg.rows import dict_row

    from app.catalog import service as catalog
    from app.catalog.models import WerkCreate
    from app.config import get_settings
    from app.ingest.service import ingest_file
    from scripts.import_mutopia import (
        download_pdf,
        map_besetzung,
        map_gattung,
        parse_year,
        safe_filename,
        sammle_stuecke,
        tags_for,
    )

    settings = get_settings()
    ctx.fortschritt(aktuell="Mutopia-Katalog wird geladen …", log_zeile=f"scope={scope}")
    stuecke = sammle_stuecke(scope, 0.3)  # blockierender Crawl (im Worker ok)
    if limit:
        stuecke = stuecke[:limit]
    ctx.fortschritt(fertig=0, gesamt=len(stuecke), aktuell="Import")

    loop = asyncio.get_event_loop()
    async with await psycopg.AsyncConnection.connect(
        os.environ["NOTEN_DATABASE_URL"], autocommit=True, row_factory=dict_row
    ) as aconn:
        cur = await aconn.execute("select kuerzel from besetzung")
        allowed = {r["kuerzel"] for r in await cur.fetchall()}
        neu = 0
        for i, p in enumerate(stuecke, 1):
            if ctx.abgebrochen():
                ctx.fortschritt(log_zeile="abgebrochen")
                return
            titel = (p["title"] or "").strip()
            komp = (p["composer"] or "").strip() or None
            try:
                if not titel:
                    continue
                cur = await aconn.execute(
                    "select 1 from werk where lower(titel)=lower(%s) and lower(coalesce(komponist,''))=lower(%s) limit 1",
                    (titel, komp or ""),
                )
                if await cur.fetchone():
                    ctx.fortschritt(fertig=i, aktuell=titel)
                    continue
                if not p["pdf"]:
                    ctx.fortschritt(fertig=i, aktuell=titel, log_zeile=f"ohne PDF: {titel}")
                    continue
                bes = map_besetzung(p["instrument"])
                if bes and allowed and bes not in allowed:
                    bes = None
                tags = tags_for(p)
                if bes is None and p["instrument"]:
                    tags.append(p["instrument"])
                werk = await catalog.create_werk(
                    aconn,
                    WerkCreate(
                        titel=titel,
                        komponist=komp,
                        gattung=map_gattung(p["instrument"], p["style"]),
                        besetzung=bes,
                        entstehungsjahr=parse_year(p["year"]),
                        notiz=f"Quelle: Mutopia Project. Stil {p['style'] or '—'}, Lizenz {p['license'] or '—'}. ID {p['id']}.",
                        tags=tags,
                    ),
                )
                aus = werk.get("ausgaben") or []
                if aus:
                    # Mutopia = gemeinfrei/CC → freigeben (druckbar)
                    await aconn.execute("update ausgabe set rechtestatus='public_domain' where id=%s", (aus[0]["id"],))
                    pdf = await loop.run_in_executor(None, download_pdf, p["pdf"])
                    await ingest_file(aconn, settings, aus[0]["id"], "scan_pdf", safe_filename(titel), pdf)
                    neu += 1
            except Exception as exc:  # noqa: BLE001
                ctx.fortschritt(log_zeile=f"übersprungen {titel[:40]}: {exc}")
            ctx.fortschritt(fertig=i, aktuell=titel)
    ctx.fortschritt(log_zeile=f"fertig — {neu} neue Werke")


def import_cpdl(conn, job, ctx):
    """Sync-Entry: importiert eine CPDL/ChoralWiki-Kategorie (MusicXML bevorzugt, sonst PDF)."""
    params = job.get("params") or {}
    category = params.get("category", "Masses")
    only_sacred = bool(params.get("only_sacred", False))
    limit = int(params.get("limit", 0) or 0)
    asyncio.run(_cpdl(ctx, category, only_sacred, limit))


async def _cpdl(ctx, category: str, only_sacred: bool, limit: int) -> None:
    import psycopg
    from psycopg.rows import dict_row

    from app.catalog import service as catalog
    from app.catalog.models import WerkCreate
    from app.config import get_settings
    from app.ingest.service import ingest_file
    from scripts.import_cpdl import build, category_titles, cpdl_file_url, download, mxl_to_plain, safe_filename, wikitexts

    settings = get_settings()
    ctx.fortschritt(aktuell=f"CPDL-Kategorie '{category}' …", log_zeile=f"category={category}")
    titles = category_titles(category)
    wt_map = await asyncio.get_event_loop().run_in_executor(None, wikitexts, titles)
    ctx.fortschritt(fertig=0, gesamt=len(titles), aktuell="Import")

    loop = asyncio.get_event_loop()
    async with await psycopg.AsyncConnection.connect(
        os.environ["NOTEN_DATABASE_URL"], autocommit=True, row_factory=dict_row
    ) as aconn:
        cur = await aconn.execute("select kuerzel from besetzung")
        allowed = {r["kuerzel"] for r in await cur.fetchall()}
        neu = 0
        for i, title in enumerate(titles, 1):
            if ctx.abgebrochen():
                ctx.fortschritt(log_zeile="abgebrochen")
                return
            if limit and neu >= limit:
                break
            titel = None
            try:
                wt = wt_map.get(title)
                if not wt:
                    ctx.fortschritt(fertig=i)
                    continue
                meta = build(title, wt, allowed)
                if not meta or not meta["titel"]:
                    ctx.fortschritt(fertig=i)
                    continue
                if only_sacred and not meta["_sacred"]:
                    ctx.fortschritt(fertig=i)
                    continue
                titel = meta["titel"]
                komp = meta["komponist"]
                fileinfo = meta.pop("_file")
                meta.pop("_sacred", None)
                if not fileinfo:
                    ctx.fortschritt(fertig=i, aktuell=titel, log_zeile=f"ohne Datei: {titel}")
                    continue
                cur = await aconn.execute(
                    "select 1 from werk where lower(titel)=lower(%s) and lower(coalesce(komponist,''))=lower(%s) limit 1",
                    (titel, komp or ""),
                )
                if await cur.fetchone():
                    ctx.fortschritt(fertig=i, aktuell=titel)
                    continue
                fn, art = fileinfo
                data = await loop.run_in_executor(None, lambda: download(cpdl_file_url(fn)))
                if fn.lower().endswith(".mxl"):
                    data = mxl_to_plain(data)
                    art = "musicxml"
                werk = await catalog.create_werk(
                    aconn,
                    WerkCreate(
                        titel=titel,
                        komponist=komp,
                        gattung=meta.get("gattung"),
                        sprache=meta.get("sprache"),
                        besetzung=meta.get("besetzung"),
                        notiz=meta.get("notiz"),
                        tags=meta.get("tags") or [],
                    ),
                )
                aus = werk.get("ausgaben") or []
                if aus:
                    await aconn.execute("update ausgabe set rechtestatus='public_domain' where id=%s", (aus[0]["id"],))
                    # ingest erkennt PDF vs. MusicXML selbst; art_hint zählt nur für PDFs
                    await ingest_file(aconn, settings, aus[0]["id"], "scan_pdf", safe_filename(titel, art), data)
                    neu += 1
            except Exception as exc:  # noqa: BLE001
                ctx.fortschritt(log_zeile=f"übersprungen {(titel or title)[:40]}: {exc}")
            ctx.fortschritt(fertig=i, aktuell=titel or title)
    ctx.fortschritt(log_zeile=f"fertig — {neu} neue Werke")
