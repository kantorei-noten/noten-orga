"""Suche: deutscher Volltext (tsvector) + Fuzzy (pg_trgm) + Facetten."""
from __future__ import annotations

from psycopg import AsyncConnection

# Facetten-Filter, die per EXISTS auf verknüpfte Tabellen wirken
_EXISTS = {
    "besetzung": "exists (select 1 from fassung f where f.werk_id = w.id and f.besetzung = %(besetzung)s)",
    "tonart": "exists (select 1 from fassung f where f.werk_id = w.id and f.tonart = %(tonart)s)",
    "schwierigkeit": "exists (select 1 from fassung f where f.werk_id = w.id and f.schwierigkeit = %(schwierigkeit)s)",
    "rechtestatus": "exists (select 1 from fassung f join ausgabe a on a.fassung_id = f.id "
    "where f.werk_id = w.id and a.rechtestatus = %(rechtestatus)s)",
    "anlass_id": "exists (select 1 from werk_anlass wa where wa.werk_id = w.id and wa.anlass_id = %(anlass_id)s)",
    "tag": "exists (select 1 from werk_tag wt join tag t on t.id = wt.tag_id where wt.werk_id = w.id and t.name = %(tag)s)",
}


def _build(q: str | None, filters: dict) -> tuple[str, dict]:
    where: list[str] = []
    params: dict = {}
    if q:
        params["q"] = q
        where.append(
            "(w.such_tsv @@ websearch_to_tsquery('deutsch_unaccent', %(q)s) "
            "or w.titel %% %(q)s "
            "or exists (select 1 from gesangbuch_eintrag g where g.werk_id = w.id and g.nummer = %(q)s))"
        )
    if filters.get("gattung"):
        params["gattung"] = filters["gattung"]
        where.append("w.gattung = %(gattung)s")
    if filters.get("sprache"):
        params["sprache"] = filters["sprache"]
        where.append("w.sprache = %(sprache)s")
    for key, sql in _EXISTS.items():
        if filters.get(key) is not None and filters.get(key) != "":
            params[key] = filters[key]
            where.append(sql)
    if filters.get("anlass_ids"):
        params["anlass_ids"] = filters["anlass_ids"]
        where.append(
            "exists (select 1 from werk_anlass wa where wa.werk_id = w.id "
            "and wa.anlass_id = any(%(anlass_ids)s))"
        )
    if filters.get("buch"):
        params["buch"] = filters["buch"]
        cond = "g.werk_id = w.id and g.buch = %(buch)s"
        if filters.get("nummer"):
            params["nummer"] = filters["nummer"]
            cond += " and g.nummer = %(nummer)s"
        where.append(f"exists (select 1 from gesangbuch_eintrag g where {cond})")
    clause = (" where " + " and ".join(where)) if where else ""
    return clause, params


async def _facetten(conn: AsyncConnection, clause: str, params: dict) -> dict:
    sql = f"""
        with treffer as (select w.id from werk w{clause})
        select 'gattung' as dim, w.gattung as wert, count(*)::int as anzahl
          from treffer t join werk w on w.id = t.id where w.gattung is not null group by w.gattung
        union all
        select 'besetzung', f.besetzung, count(distinct t.id)::int
          from treffer t join fassung f on f.werk_id = t.id where f.besetzung is not null group by f.besetzung
        union all
        select 'rechtestatus', a.rechtestatus, count(distinct t.id)::int
          from treffer t join fassung f on f.werk_id = t.id join ausgabe a on a.fassung_id = f.id
          group by a.rechtestatus
        union all
        select 'anlass', a.name, count(distinct t.id)::int
          from treffer t join werk_anlass wa on wa.werk_id = t.id join anlass a on a.id = wa.anlass_id
          group by a.name
    """
    cur = await conn.execute(sql, params)
    out: dict[str, list] = {"gattung": [], "besetzung": [], "rechtestatus": [], "anlass": []}
    for row in await cur.fetchall():
        out[row["dim"]].append({"wert": row["wert"], "anzahl": row["anzahl"]})
    for key in out:
        out[key].sort(key=lambda x: x["anzahl"], reverse=True)
    return out


async def _descendant_anlass_ids(conn: AsyncConnection, anlass_id) -> list:
    cur = await conn.execute(
        """with recursive sub as (
             select id from anlass where id = %s
             union all
             select a.id from anlass a join sub on a.parent_id = sub.id)
           select id from sub""",
        (anlass_id,),
    )
    return [r["id"] for r in await cur.fetchall()]


async def suche(
    conn: AsyncConnection,
    q: str | None,
    filters: dict,
    limit: int = 50,
    offset: int = 0,
    anlass_rekursiv: bool = False,
) -> dict:
    filters = dict(filters)
    if anlass_rekursiv and filters.get("anlass_id"):
        # Anlass + alle Unter-Anlässe (Kirchenjahr-Hierarchie) einbeziehen
        filters["anlass_ids"] = await _descendant_anlass_ids(conn, filters.pop("anlass_id"))
    clause, params = _build(q, filters)
    rang = (
        "ts_rank(w.such_tsv, websearch_to_tsquery('deutsch_unaccent', %(q)s)) "
        "+ similarity(w.titel, %(q)s)"
        if q
        else "0"
    )

    cur = await conn.execute(f"select count(*)::int as n from werk w{clause}", params)
    total = (await cur.fetchone())["n"]

    page = dict(params, _limit=limit, _offset=offset)
    cur = await conn.execute(
        f"""select w.id, w.titel, w.komponist, w.gattung, ({rang}) as rang,
              coalesce(array_agg(distinct (ge.buch || ' ' || ge.nummer))
                       filter (where ge.id is not null), '{{}}') as gesangbuch
            from werk w left join gesangbuch_eintrag ge on ge.werk_id = w.id
            {clause}
            group by w.id order by rang desc, w.titel
            limit %(_limit)s offset %(_offset)s""",
        page,
    )
    ergebnisse = await cur.fetchall()
    facetten = await _facetten(conn, clause, params)
    return {"total": total, "ergebnisse": ergebnisse, "facetten": facetten}
