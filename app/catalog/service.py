"""Katalog-Logik: Werke anlegen/lesen/ändern, Dubletten, Batch, CSV."""
from __future__ import annotations

import csv
import io
import re

from psycopg import AsyncConnection

from .models import GesangbuchEintragIn, WerkCreate, WerkUpdate


async def _tag_id(conn: AsyncConnection, name: str):
    cur = await conn.execute(
        "insert into tag (name) values (%s) on conflict (name) do update set name = excluded.name returning id",
        (name.strip(),),
    )
    return (await cur.fetchone())["id"]


async def _attach(conn: AsyncConnection, werk_id, data: WerkCreate) -> None:
    for e in data.gesangbuch:
        await conn.execute(
            "insert into gesangbuch_eintrag (werk_id, buch, nummer, teil) values (%s,%s,%s,%s) "
            "on conflict do nothing",
            (werk_id, e.buch, e.nummer, e.teil),
        )
    for name in {t.strip() for t in data.tags if t.strip()}:
        tid = await _tag_id(conn, name)
        await conn.execute(
            "insert into werk_tag (werk_id, tag_id) values (%s,%s) on conflict do nothing",
            (werk_id, tid),
        )
    for aid in data.anlass_ids:
        await conn.execute(
            "insert into werk_anlass (werk_id, anlass_id) values (%s,%s) on conflict do nothing",
            (werk_id, aid),
        )


async def create_werk(conn: AsyncConnection, data: WerkCreate) -> dict:
    async with conn.transaction():
        cur = await conn.execute(
            """insert into werk (titel, komponist, textdichter, gattung, sprache, entstehungsjahr, notiz)
               values (%s,%s,%s,%s,%s,%s,%s) returning id""",
            (data.titel, data.komponist, data.textdichter, data.gattung,
             data.sprache, data.entstehungsjahr, data.notiz),
        )
        werk_id = (await cur.fetchone())["id"]
        cur = await conn.execute(
            "insert into fassung (werk_id, besetzung, tonart, schwierigkeit) values (%s,%s,%s,%s) returning id",
            (werk_id, data.besetzung, data.tonart, data.schwierigkeit),
        )
        fassung_id = (await cur.fetchone())["id"]
        await conn.execute(
            "insert into ausgabe (fassung_id, bevorzugt) values (%s, true)", (fassung_id,)
        )
        await _attach(conn, werk_id, data)
    return await get_werk(conn, werk_id)


async def extrahiere_liedtext(conn: AsyncConnection, werk_id) -> str:
    """Liedtext-Vorschlag aus den Notenblättern des Werks (PDF-Textebene / MusicXML)."""
    cur = await conn.execute(
        """select d.pfad, d.art from datei d
           join ausgabe a on a.id = d.ausgabe_id
           join fassung f on f.id = a.fassung_id
           where f.werk_id = %s and d.art in ('scan_pdf','import_pdf','musicxml')
           order by (d.art = 'musicxml') desc, d.created_at""",
        (werk_id,),
    )
    dateien = [(r["pfad"], r["art"]) for r in await cur.fetchall()]
    if not dateien:
        return ""
    import anyio

    from ..config import get_settings
    from . import lyrics

    return await anyio.to_thread.run_sync(lyrics.beste_extraktion, dateien, get_settings())


async def erzeuge_chordpro(conn: AsyncConnection, werk_id) -> tuple[str, str]:
    """ChordPro-Vorschlag aus den MusicXML-Noten des Werks.

    Wählt automatisch die beste Engine: music21 (Harmonieanalyse), *wenn installiert*,
    sonst den schlanken Eigen-Analyzer. Rückgabe: (text, engine) mit engine ∈
    {"music21", "basis", ""} (leer, wenn kein Vorschlag entstand)."""
    cur = await conn.execute("select titel from werk where id = %s", (werk_id,))
    w = await cur.fetchone()
    if not w:
        return "", ""
    cur = await conn.execute(
        """select d.pfad from datei d
           join ausgabe a on a.id = d.ausgabe_id
           join fassung f on f.id = a.fassung_id
           where f.werk_id = %s and d.art = 'musicxml'
           order by d.created_at""",
        (werk_id,),
    )
    pfade = [r["pfad"] for r in await cur.fetchall()][:10]
    if not pfade:
        return "", ""
    import anyio

    from ..config import get_settings
    from ..ingest import sandbox
    from . import chordgen

    settings = get_settings()
    use_m21 = chordgen.music21_verfuegbar()

    def _best(pfade: list[str], titel: str) -> tuple[str, str]:
        best = ""
        best_engine = ""
        for p in pfade:
            t = ""
            engine = ""
            if use_m21:
                # music21 NUR isoliert im Sandbox-Subprozess (RLIMIT_AS/CPU + Timeout),
                # weil es MusicXML ohne defusedxml parst — eine bösartige Datei darf den
                # API-Prozess nicht per Speicher-/CPU-Bombe treffen.
                try:
                    with open(p, "rb") as fh:
                        data = fh.read()
                    res = sandbox.run(
                        ["chordpro", titel or "", "400"],
                        data,
                        settings,
                        worker="app.ingest.music21_worker",
                    )
                    t = res.get("text", "") or ""
                    engine = "music21" if t.strip() else ""
                except Exception:
                    t, engine = "", ""
            if not t.strip():  # Fallback: gehärteter Eigen-Analyzer (defusedxml)
                try:
                    t = chordgen.chordpro_aus_musicxml(p, titel)
                    engine = "basis" if t.strip() else ""
                except Exception:
                    t, engine = "", ""
            if len(t) > len(best):
                best, best_engine = t, engine
        return best, best_engine

    return await anyio.to_thread.run_sync(_best, pfade, w["titel"])


async def set_projektionstext(conn: AsyncConnection, werk_id, text: str | None) -> dict | None:
    cur = await conn.execute(
        "update werk set projektionstext = %s, updated_at = now() where id = %s returning id",
        (text, werk_id),
    )
    if not await cur.fetchone():
        return None
    return await get_werk(conn, werk_id)


async def get_werk(conn: AsyncConnection, werk_id) -> dict | None:
    cur = await conn.execute("select * from werk where id = %s", (werk_id,))
    werk = await cur.fetchone()
    if not werk:
        return None
    werk.pop("such_tsv", None)

    cur = await conn.execute(
        "select buch, nummer, teil from gesangbuch_eintrag where werk_id = %s order by buch, nummer",
        (werk_id,),
    )
    werk["gesangbuch"] = await cur.fetchall()

    cur = await conn.execute(
        "select t.name from werk_tag wt join tag t on t.id = wt.tag_id where wt.werk_id = %s order by t.name",
        (werk_id,),
    )
    werk["tags"] = [r["name"] for r in await cur.fetchall()]

    cur = await conn.execute(
        "select a.id, a.name from werk_anlass wa join anlass a on a.id = wa.anlass_id where wa.werk_id = %s",
        (werk_id,),
    )
    werk["anlass"] = await cur.fetchall()

    cur = await conn.execute(
        """select au.id, au.name, au.rechtestatus, au.bevorzugt, au.omr_status,
                  f.besetzung, f.tonart, f.schwierigkeit
           from ausgabe au join fassung f on f.id = au.fassung_id
           where f.werk_id = %s order by au.bevorzugt desc, au.created_at""",
        (werk_id,),
    )
    ausgaben = await cur.fetchall()
    for au in ausgaben:
        cur = await conn.execute(
            "select id, art, mime, seiten, original_name, (thumb_pfad is not null) as hat_vorschau "
            "from datei where ausgabe_id = %s order by created_at",
            (au["id"],),
        )
        au["dateien"] = await cur.fetchall()
    werk["ausgaben"] = ausgaben
    return werk


async def werk_baum(conn: AsyncConnection, feld: str) -> list[dict]:
    """Gruppierter Katalog-Baum: [{gruppe, anzahl, werke:[{id,titel}]}] nach Komponist/Gattung/Anlass."""
    if feld == "anlass":
        cur = await conn.execute(
            """select coalesce(a.name, '— ohne Anlass —') as gruppe, w.id, w.titel
               from werk w
               left join werk_anlass wa on wa.werk_id = w.id
               left join anlass a on a.id = wa.anlass_id
               order by gruppe, w.titel"""
        )
    else:
        col = "komponist" if feld == "komponist" else "gattung"
        cur = await conn.execute(
            f"""select coalesce(nullif(trim(w.{col}), ''), '— ohne Angabe —') as gruppe, w.id, w.titel
                from werk w order by gruppe, w.titel"""
        )
    baum: list[dict] = []
    idx: dict[str, dict] = {}
    for r in await cur.fetchall():
        g = r["gruppe"]
        grp = idx.get(g)
        if grp is None:
            grp = {"gruppe": g, "werke": []}
            idx[g] = grp
            baum.append(grp)
        grp["werke"].append({"id": str(r["id"]), "titel": r["titel"]})
    for grp in baum:
        grp["anzahl"] = len(grp["werke"])
    return baum


async def list_werke(conn: AsyncConnection, limit: int = 50, offset: int = 0) -> list[dict]:
    cur = await conn.execute(
        """select w.id, w.titel, w.komponist, w.gattung, w.created_at,
             coalesce(array_agg(distinct (ge.buch || ' ' || ge.nummer))
                      filter (where ge.id is not null), '{}') as gesangbuch
           from werk w left join gesangbuch_eintrag ge on ge.werk_id = w.id
           group by w.id order by w.titel limit %s offset %s""",
        (limit, offset),
    )
    return await cur.fetchall()


async def update_werk(conn: AsyncConnection, werk_id, data: WerkUpdate) -> dict | None:
    fields = data.model_dump(exclude_unset=True)
    if fields:
        sets = ", ".join(f"{k} = %s" for k in fields)
        await conn.execute(
            f"update werk set {sets} where id = %s", (*fields.values(), werk_id)
        )
    return await get_werk(conn, werk_id)


async def delete_werk(conn: AsyncConnection, werk_id) -> bool:
    cur = await conn.execute("delete from werk where id = %s", (werk_id,))
    return cur.rowcount > 0


async def aehnliche_werke(conn: AsyncConnection, titel: str, limit: int = 5) -> list[dict]:
    """Dubletten-Warnung: ähnliche Titel via pg_trgm."""
    cur = await conn.execute(
        """select id, titel, komponist, round(similarity(titel, %(t)s)::numeric, 3) as aehnlichkeit
           from werk where titel %% %(t)s
           order by aehnlichkeit desc limit %(l)s""",
        {"t": titel, "l": limit},
    )
    return await cur.fetchall()


async def batch_add_tag(conn: AsyncConnection, werk_ids: list, tag: str) -> int:
    tid = await _tag_id(conn, tag)
    n = 0
    for wid in werk_ids:
        cur = await conn.execute(
            "insert into werk_tag (werk_id, tag_id) values (%s,%s) on conflict do nothing",
            (wid, tid),
        )
        n += cur.rowcount
    return n


async def batch_set_anlass(conn: AsyncConnection, werk_ids: list, anlass_id) -> int:
    n = 0
    for wid in werk_ids:
        cur = await conn.execute(
            "insert into werk_anlass (werk_id, anlass_id) values (%s,%s) on conflict do nothing",
            (wid, anlass_id),
        )
        n += cur.rowcount
    return n


# --- CSV ---
def _split_cell(cell: str | None) -> list[str]:
    return [x.strip() for x in re.split(r"[;,]", cell or "") if x.strip()]


async def export_csv(conn: AsyncConnection) -> str:
    cur = await conn.execute(
        """select w.titel, w.komponist, w.textdichter, w.gattung, w.sprache, w.entstehungsjahr, w.notiz,
             coalesce(string_agg(distinct case when ge.buch='GL' then ge.nummer end, '; '), '') as gl,
             coalesce(string_agg(distinct case when ge.buch='EG' then ge.nummer end, '; '), '') as eg,
             coalesce(string_agg(distinct t.name, '; '), '') as tags
           from werk w
           left join gesangbuch_eintrag ge on ge.werk_id = w.id
           left join werk_tag wt on wt.werk_id = w.id
           left join tag t on t.id = wt.tag_id
           group by w.id order by w.titel"""
    )
    rows = await cur.fetchall()
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(
        ["titel", "komponist", "textdichter", "gattung", "sprache",
         "entstehungsjahr", "GL", "EG", "tags", "notiz"]
    )
    for r in rows:
        writer.writerow([
            r["titel"], r["komponist"] or "", r["textdichter"] or "", r["gattung"] or "",
            r["sprache"] or "", r["entstehungsjahr"] or "", r["gl"], r["eg"],
            r["tags"], r["notiz"] or "",
        ])
    return buf.getvalue()


async def import_csv(conn: AsyncConnection, content: bytes) -> dict:
    text = content.decode("utf-8-sig")
    sample = text[:2000]
    delim = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    created = skipped = 0
    errors: list[str] = []
    for i, row in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): v for k, v in row.items()}
        titel = (row.get("titel") or "").strip()
        if not titel:
            errors.append(f"Zeile {i}: kein Titel")
            continue
        komponist = (row.get("komponist") or "").strip() or None
        cur = await conn.execute(
            "select 1 from werk where lower(titel) = lower(%s) "
            "and coalesce(komponist,'') = coalesce(%s,'')",
            (titel, komponist),
        )
        if await cur.fetchone():
            skipped += 1
            continue
        gesang = [GesangbuchEintragIn(buch="GL", nummer=n) for n in _split_cell(row.get("gl"))]
        gesang += [GesangbuchEintragIn(buch="EG", nummer=n) for n in _split_cell(row.get("eg"))]
        try:
            jahr = int(row["entstehungsjahr"]) if (row.get("entstehungsjahr") or "").strip() else None
        except ValueError:
            jahr = None
        data = WerkCreate(
            titel=titel,
            komponist=komponist,
            textdichter=(row.get("textdichter") or "").strip() or None,
            gattung=(row.get("gattung") or "").strip() or None,
            sprache=(row.get("sprache") or "de").strip() or "de",
            entstehungsjahr=jahr,
            notiz=(row.get("notiz") or "").strip() or None,
            gesangbuch=gesang,
            tags=_split_cell(row.get("tags")),
        )
        try:
            await create_werk(conn, data)
            created += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Zeile {i}: {exc}")
    return {"angelegt": created, "uebersprungen": skipped, "fehler": errors}
