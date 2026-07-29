"""Job-Handler des Workers. Schwere Abhängigkeiten (music21) werden LAZY importiert,
damit die Registrierung ohne sie funktioniert.

Registry-Muster: @handler("typ") registriert eine Funktion (conn, job, ctx).
`ctx.fortschritt(fertig, gesamt, aktuell, log_zeile)` schreibt den Fortschritt zurück.
"""
from __future__ import annotations

REGISTRY: dict = {}


def handler(typ: str):
    def deco(fn):
        REGISTRY[typ] = fn
        return fn

    return deco


@handler("import_bach")
def import_bach(conn, job, ctx):
    """Bach-Choräle aus dem music21-Corpus importieren (kein externer Crawl)."""
    from .bach_import import run

    run(conn, ctx)


@handler("import_mutopia")
def import_mutopia(conn, job, ctx):
    """Gemeinfreie Noten vom Mutopia Project importieren (A4-PDF)."""
    from .imports import import_mutopia as _run

    _run(conn, job, ctx)


@handler("import_cpdl")
def import_cpdl(conn, job, ctx):
    """CPDL/ChoralWiki-Kategorie importieren (params.category, z. B. 'Masses')."""
    from .imports import import_cpdl as _run

    _run(conn, job, ctx)


@handler("chordpro_music21")
def chordpro_music21(conn, job, ctx):
    """Erzeugt für alle Werke mit MusicXML (und noch ohne ChordPro) einen ChordPro-Text
    per music21-Harmonieanalyse und speichert ihn in die chordpro-Tabelle."""
    from .music21_chordpro import werk_chordpro  # lazy: music21 nur im Worker-Image

    cur = conn.execute(
        """select distinct w.id, w.titel from werk w
           join fassung f on f.werk_id = w.id
           join ausgabe a on a.fassung_id = f.id
           join datei d on d.ausgabe_id = a.id and d.art = 'musicxml'
           where not exists (select 1 from chordpro c where c.werk_id = w.id and coalesce(c.text,'') <> '')
           order by w.titel"""
    )
    werke = cur.fetchall()
    ctx.fortschritt(fertig=0, gesamt=len(werke), aktuell="Start", log_zeile=f"{len(werke)} Werke ohne ChordPro")
    for i, w in enumerate(werke, 1):
        if ctx.abgebrochen():
            ctx.fortschritt(log_zeile="abgebrochen")
            return
        cur = conn.execute(
            """select d.pfad from datei d join ausgabe a on a.id = d.ausgabe_id
               join fassung f on f.id = a.fassung_id
               where f.werk_id = %s and d.art = 'musicxml' order by d.created_at limit 1""",
            (w["id"],),
        )
        row = cur.fetchone()
        if row:
            try:
                text = werk_chordpro(row["pfad"], w["titel"])
                if text.strip():
                    conn.execute(
                        """insert into chordpro (werk_id, text) values (%s, %s)
                           on conflict (werk_id) do update set text = excluded.text""",
                        (w["id"], text),
                    )
            except Exception as exc:  # noqa: BLE001
                ctx.fortschritt(log_zeile=f"übersprungen: {w['titel']}: {exc}")
        ctx.fortschritt(fertig=i, aktuell=w["titel"])
