"""Setlisten-Logik: CRUD, Einträge (Stücke/Abschnitte), Reihenfolge, Auflösung."""
from __future__ import annotations

from psycopg import AsyncConnection

from .models import EintragCreate, SetlisteCreate, SetlisteUpdate


async def create_setliste(conn: AsyncConnection, data: SetlisteCreate) -> dict:
    cur = await conn.execute(
        "insert into setliste (name, datum, anlass_id, notiz) values (%s,%s,%s,%s) returning *",
        (data.name, data.datum, data.anlass_id, data.notiz),
    )
    return await cur.fetchone()


async def list_setlisten(conn: AsyncConnection) -> list[dict]:
    cur = await conn.execute(
        """select s.*, count(e.id)::int as anzahl_eintraege
           from setliste s left join setliste_eintrag e on e.setliste_id = s.id
           group by s.id order by s.datum desc nulls last, s.name"""
    )
    return await cur.fetchall()


async def _resolve_eintrag(conn: AsyncConnection, e: dict) -> dict:
    """Ergänzt Werk-Titel und löst die anzuzeigende Datei auf (bevorzugte Ausgabe)."""
    if e.get("werk_id"):
        cur = await conn.execute(
            "select titel, komponist, projektionstext from werk where id = %s", (e["werk_id"],)
        )
        w = await cur.fetchone()
        e["werk_titel"] = w["titel"] if w else None
        e["komponist"] = w["komponist"] if w else None
        e["projektionstext"] = w["projektionstext"] if w else None

        # Tatsächlich gepinntes Blatt (roh aus DB, vor Auto-Auflösung) für die Bearbeiten-Maske
        e["gepinnt_datei_id"] = e.get("datei_id")

        # Gepinntes Blatt: genau diese Datei verwenden
        pinned = e.get("datei_id")
        if pinned:
            cur = await conn.execute(
                "select seiten, ausgabe_id, original_name from datei where id = %s", (pinned,)
            )
            d = await cur.fetchone()
            if d:
                e["seiten"] = d["seiten"]
                e["aufgeloeste_ausgabe_id"] = d["ausgabe_id"]
                e["blatt_name"] = d.get("original_name")
            return e

        ausgabe_id = e.get("ausgabe_id")
        if not ausgabe_id:
            cur = await conn.execute(
                """select au.id from ausgabe au join fassung f on f.id = au.fassung_id
                   where f.werk_id = %s order by au.bevorzugt desc, au.created_at limit 1""",
                (e["werk_id"],),
            )
            row = await cur.fetchone()
            ausgabe_id = row["id"] if row else None
        e["aufgeloeste_ausgabe_id"] = ausgabe_id

        if ausgabe_id:
            cur = await conn.execute(
                """select id, seiten from datei
                   where ausgabe_id = %s and art in ('scan_pdf','import_pdf')
                   order by (art = 'scan_pdf') desc, created_at limit 1""",
                (ausgabe_id,),
            )
            d = await cur.fetchone()
            e["datei_id"] = d["id"] if d else None
            e["seiten"] = d["seiten"] if d else None
    return e


async def get_setliste(conn: AsyncConnection, setliste_id) -> dict | None:
    cur = await conn.execute("select * from setliste where id = %s", (setliste_id,))
    s = await cur.fetchone()
    if not s:
        return None
    cur = await conn.execute(
        "select * from setliste_eintrag where setliste_id = %s order by position", (setliste_id,)
    )
    s["eintraege"] = [await _resolve_eintrag(conn, e) for e in await cur.fetchall()]
    return s


async def update_setliste(conn: AsyncConnection, setliste_id, data: SetlisteUpdate) -> dict | None:
    fields = data.model_dump(exclude_unset=True)
    if fields:
        sets = ", ".join(f"{k} = %s" for k in fields)
        await conn.execute(
            f"update setliste set {sets} where id = %s", (*fields.values(), setliste_id)
        )
    return await get_setliste(conn, setliste_id)


async def delete_setliste(conn: AsyncConnection, setliste_id) -> bool:
    cur = await conn.execute("delete from setliste where id = %s", (setliste_id,))
    return cur.rowcount > 0


async def add_eintrag(conn: AsyncConnection, setliste_id, data: EintragCreate) -> dict | None:
    cur = await conn.execute("select 1 from setliste where id = %s", (setliste_id,))
    if not await cur.fetchone():
        return None
    cur = await conn.execute(
        "select coalesce(max(position), 0) + 1 as pos from setliste_eintrag where setliste_id = %s",
        (setliste_id,),
    )
    pos = (await cur.fetchone())["pos"]
    cur = await conn.execute(
        """insert into setliste_eintrag
             (setliste_id, position, typ, werk_id, ausgabe_id, datei_id, titel, seite_von, seite_bis)
           values (%s,%s,%s,%s,%s,%s,%s,%s,%s) returning *""",
        (setliste_id, pos, data.typ, data.werk_id, data.ausgabe_id, data.datei_id,
         data.titel, data.seite_von, data.seite_bis),
    )
    return await _resolve_eintrag(conn, await cur.fetchone())


async def update_eintrag(conn: AsyncConnection, setliste_id, eintrag_id, data) -> dict | None:
    """Bearbeitet einen bestehenden Eintrag (Blatt umhängen, Seitenbereich, Titel)."""
    cur = await conn.execute(
        "select * from setliste_eintrag where id = %s and setliste_id = %s",
        (eintrag_id, setliste_id),
    )
    row = await cur.fetchone()
    if not row:
        return None
    fields = data.model_dump(exclude_unset=True)
    allowed = {k: v for k, v in fields.items() if k in ("datei_id", "titel", "seite_von", "seite_bis")}
    if allowed:
        sets = ", ".join(f"{k} = %s" for k in allowed)
        cur = await conn.execute(
            f"update setliste_eintrag set {sets} where id = %s and setliste_id = %s returning *",
            (*allowed.values(), eintrag_id, setliste_id),
        )
        row = await cur.fetchone()
    return await _resolve_eintrag(conn, row)


async def remove_eintrag(conn: AsyncConnection, setliste_id, eintrag_id) -> bool:
    cur = await conn.execute(
        "delete from setliste_eintrag where id = %s and setliste_id = %s",
        (eintrag_id, setliste_id),
    )
    return cur.rowcount > 0


async def reorder(conn: AsyncConnection, setliste_id, eintrag_ids: list) -> dict | None:
    async with conn.transaction():
        for idx, eid in enumerate(eintrag_ids, start=1):
            await conn.execute(
                "update setliste_eintrag set position = %s where id = %s and setliste_id = %s",
                (idx, eid, setliste_id),
            )
    return await get_setliste(conn, setliste_id)
