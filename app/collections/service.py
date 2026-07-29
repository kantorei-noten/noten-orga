"""Sammlungen: Unter-Bibliotheken (Orgel/Chor/Gemeinde/Anlass) neben Setlisten."""
from __future__ import annotations

from psycopg import AsyncConnection


async def create_sammlung(conn: AsyncConnection, name: str, art: str, notiz: str | None) -> dict:
    cur = await conn.execute(
        "insert into sammlung (name, art, notiz) values (%s,%s,%s) returning *",
        (name, art, notiz),
    )
    return await cur.fetchone()


async def list_sammlungen(conn: AsyncConnection) -> list[dict]:
    cur = await conn.execute(
        """select s.*, sa.name as art_name, count(ws.werk_id)::int as anzahl_werke
           from sammlung s
           left join sammlung_art sa on sa.kuerzel = s.art
           left join werk_sammlung ws on ws.sammlung_id = s.id
           group by s.id, sa.name order by s.art, s.name"""
    )
    return await cur.fetchall()


async def get_sammlung(conn: AsyncConnection, sammlung_id) -> dict | None:
    cur = await conn.execute(
        """select s.*, sa.name as art_name from sammlung s
           left join sammlung_art sa on sa.kuerzel = s.art where s.id = %s""",
        (sammlung_id,),
    )
    s = await cur.fetchone()
    if not s:
        return None
    cur = await conn.execute(
        """select w.id, w.titel, w.komponist from werk_sammlung ws
           join werk w on w.id = ws.werk_id where ws.sammlung_id = %s order by w.titel""",
        (sammlung_id,),
    )
    s["werke"] = await cur.fetchall()
    return s


async def update_sammlung(conn: AsyncConnection, sammlung_id, fields: dict) -> dict | None:
    if fields:
        sets = ", ".join(f"{k} = %s" for k in fields)
        await conn.execute(
            f"update sammlung set {sets} where id = %s", (*fields.values(), sammlung_id)
        )
    return await get_sammlung(conn, sammlung_id)


async def delete_sammlung(conn: AsyncConnection, sammlung_id) -> bool:
    cur = await conn.execute("delete from sammlung where id = %s", (sammlung_id,))
    return cur.rowcount > 0


async def add_werk(conn: AsyncConnection, sammlung_id, werk_id) -> bool:
    cur = await conn.execute(
        "insert into werk_sammlung (werk_id, sammlung_id) values (%s,%s) on conflict do nothing",
        (werk_id, sammlung_id),
    )
    return cur.rowcount > 0


async def remove_werk(conn: AsyncConnection, sammlung_id, werk_id) -> bool:
    cur = await conn.execute(
        "delete from werk_sammlung where werk_id = %s and sammlung_id = %s",
        (werk_id, sammlung_id),
    )
    return cur.rowcount > 0
