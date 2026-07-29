"""Annotationen: benennbare Ebenen als SVG-Overlay pro Ausgabe/Seite/Benutzer.

Objekt-ACL: jeder Nutzer sieht/ändert ausschließlich seine eigenen Annotationen.
Nie ins Original-PDF geschrieben (Archivtreue).
"""
from __future__ import annotations

from psycopg import AsyncConnection
from psycopg.types.json import Json


async def seiten_mit_inhalt(conn: AsyncConnection, ausgabe_id, benutzer_id) -> list[int]:
    """Seitenzahlen, auf denen der Benutzer echte Notizen hat (Striche oder Texte)."""
    cur = await conn.execute(
        """select distinct seite from annotation
           where ausgabe_id = %s and benutzer_id = %s and (
             (jsonb_typeof(daten->'strokes') = 'array' and jsonb_array_length(daten->'strokes') > 0) or
             (jsonb_typeof(daten->'texts')   = 'array' and jsonb_array_length(daten->'texts')   > 0) or
             (jsonb_typeof(daten->'paths')   = 'array' and jsonb_array_length(daten->'paths')   > 0)
           )
           order by seite""",
        (ausgabe_id, benutzer_id),
    )
    return [r["seite"] for r in await cur.fetchall()]


async def list_for_page(conn: AsyncConnection, ausgabe_id, benutzer_id, seite: int) -> list[dict]:
    cur = await conn.execute(
        "select id, ebene, seite, daten, sichtbar from annotation "
        "where ausgabe_id = %s and benutzer_id = %s and seite = %s order by ebene",
        (ausgabe_id, benutzer_id, seite),
    )
    return await cur.fetchall()


async def upsert(
    conn: AsyncConnection, ausgabe_id, benutzer_id, ebene: str, seite: int, daten: dict, geteilt: bool = False
) -> dict:
    cur = await conn.execute(
        """insert into annotation (ausgabe_id, benutzer_id, ebene, seite, daten, geteilt)
           values (%s, %s, %s, %s, %s, %s)
           on conflict (ausgabe_id, benutzer_id, ebene, seite)
           do update set daten = excluded.daten, geteilt = excluded.geteilt, updated_at = now()
           returning id, ebene, seite, daten, sichtbar, geteilt""",
        (ausgabe_id, benutzer_id, ebene, seite, Json(daten), geteilt),
    )
    return await cur.fetchone()


async def list_geteilt(conn: AsyncConnection, ausgabe_id, seite: int) -> list[dict]:
    """Geteilte Ebenen (z. B. Chorleiter-Anweisungen) — für alle Sänger sichtbar."""
    cur = await conn.execute(
        "select id, ebene, seite, daten, benutzer_id from annotation "
        "where ausgabe_id = %s and seite = %s and geteilt = true order by ebene",
        (ausgabe_id, seite),
    )
    return await cur.fetchall()


async def delete(conn: AsyncConnection, ann_id, benutzer_id) -> bool:
    cur = await conn.execute(
        "delete from annotation where id = %s and benutzer_id = %s", (ann_id, benutzer_id)
    )
    return cur.rowcount > 0
