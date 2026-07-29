"""Gruppen (Chor/Bläser/Band) und Dienstplanung — ganze Gruppe als EIN Dienst."""
from __future__ import annotations

from psycopg import AsyncConnection


async def create_gruppe(conn: AsyncConnection, name: str, art: str) -> dict:
    cur = await conn.execute(
        "insert into gruppe (name, art) values (%s,%s) returning *", (name, art)
    )
    return await cur.fetchone()


async def list_gruppen(conn: AsyncConnection) -> list[dict]:
    cur = await conn.execute(
        """select g.*,
             count(b.id)::int as anzahl_mitglieder,
             coalesce(
               json_agg(json_build_object('id', b.id, 'benutzername', b.benutzername)
                        order by b.benutzername) filter (where b.id is not null),
               '[]') as mitglieder
           from gruppe g
           left join gruppe_mitglied gm on gm.gruppe_id = g.id
           left join benutzer b on b.id = gm.benutzer_id
           group by g.id order by g.name"""
    )
    return await cur.fetchall()


async def delete_gruppe(conn: AsyncConnection, gruppe_id) -> bool:
    cur = await conn.execute("delete from gruppe where id = %s", (gruppe_id,))
    return cur.rowcount > 0


async def delete_dienst(conn: AsyncConnection, dienst_id) -> bool:
    cur = await conn.execute("delete from dienst where id = %s", (dienst_id,))
    return cur.rowcount > 0


async def add_mitglied(conn: AsyncConnection, gruppe_id, benutzer_id) -> bool:
    cur = await conn.execute(
        "insert into gruppe_mitglied (gruppe_id, benutzer_id) values (%s,%s) on conflict do nothing",
        (gruppe_id, benutzer_id),
    )
    return cur.rowcount > 0


async def remove_mitglied(conn: AsyncConnection, gruppe_id, benutzer_id) -> bool:
    cur = await conn.execute(
        "delete from gruppe_mitglied where gruppe_id = %s and benutzer_id = %s",
        (gruppe_id, benutzer_id),
    )
    return cur.rowcount > 0


async def create_dienst(conn: AsyncConnection, gruppe_id, setliste_id, datum, notiz) -> dict:
    cur = await conn.execute(
        """insert into dienst (gruppe_id, setliste_id, datum, notiz)
           values (%s,%s,%s,%s) returning *""",
        (gruppe_id, setliste_id, datum, notiz),
    )
    return await cur.fetchone()


_TEILNEHMER_SUBQUERY = """
    coalesce((
      select json_agg(json_build_object(
               'id', b.id, 'benutzername', b.benutzername,
               'status', coalesce(z.status, 'offen'), 'notiz', z.notiz)
             order by b.benutzername)
      from gruppe_mitglied gm
      join benutzer b on b.id = gm.benutzer_id
      left join dienst_zusage z on z.dienst_id = d.id and z.benutzer_id = b.id
      where gm.gruppe_id = d.gruppe_id
    ), '[]') as teilnehmer
"""


async def list_dienste(conn: AsyncConnection) -> list[dict]:
    cur = await conn.execute(
        f"""select d.*, g.name as gruppe_name, s.name as setliste_name,
             (select count(*)::int from gruppe_mitglied gm where gm.gruppe_id = d.gruppe_id) as anzahl_mitglieder,
             {_TEILNEHMER_SUBQUERY}
           from dienst d join gruppe g on g.id = d.gruppe_id
           left join setliste s on s.id = d.setliste_id
           order by d.datum desc nulls last, d.created_at desc"""
    )
    return await cur.fetchall()


async def meine_dienste(conn: AsyncConnection, benutzer_id) -> list[dict]:
    """Dienste, bei denen der Nutzer (über die Gruppe) eingetragen ist, inkl. seiner Zusage."""
    cur = await conn.execute(
        """select d.*, g.name as gruppe_name, s.name as setliste_name,
             coalesce(z.status, 'offen') as mein_status, z.notiz as meine_notiz
           from dienst d
           join gruppe g on g.id = d.gruppe_id
           join gruppe_mitglied gm on gm.gruppe_id = d.gruppe_id and gm.benutzer_id = %s
           left join setliste s on s.id = d.setliste_id
           left join dienst_zusage z on z.dienst_id = d.id and z.benutzer_id = %s
           order by d.datum asc nulls last, d.created_at desc""",
        (benutzer_id, benutzer_id),
    )
    return await cur.fetchall()


async def ist_mitglied(conn: AsyncConnection, dienst_id, benutzer_id) -> bool:
    cur = await conn.execute(
        """select 1 from dienst d
           join gruppe_mitglied gm on gm.gruppe_id = d.gruppe_id
           where d.id = %s and gm.benutzer_id = %s""",
        (dienst_id, benutzer_id),
    )
    return await cur.fetchone() is not None


async def set_zusage(conn: AsyncConnection, dienst_id, benutzer_id, status: str, notiz) -> dict:
    cur = await conn.execute(
        """insert into dienst_zusage (dienst_id, benutzer_id, status, notiz)
           values (%s,%s,%s,%s)
           on conflict (dienst_id, benutzer_id)
           do update set status = excluded.status, notiz = excluded.notiz, updated_at = now()
           returning dienst_id, benutzer_id, status, notiz""",
        (dienst_id, benutzer_id, status, notiz),
    )
    return await cur.fetchone()


async def update_dienst(conn: AsyncConnection, dienst_id, fields: dict) -> dict | None:
    allowed = {k: v for k, v in fields.items() if k in ("datum", "setliste_id", "notiz", "bestaetigt")}
    if allowed:
        sets = ", ".join(f"{k} = %s" for k in allowed)
        await conn.execute(
            f"update dienst set {sets} where id = %s", (*allowed.values(), dienst_id)
        )
    cur = await conn.execute(
        f"""select d.*, g.name as gruppe_name, s.name as setliste_name,
             (select count(*)::int from gruppe_mitglied gm where gm.gruppe_id = d.gruppe_id) as anzahl_mitglieder,
             {_TEILNEHMER_SUBQUERY}
           from dienst d join gruppe g on g.id = d.gruppe_id
           left join setliste s on s.id = d.setliste_id
           where d.id = %s""",
        (dienst_id,),
    )
    return await cur.fetchone()
