"""Import der Bach-Choräle aus dem music21-Corpus — als Worker-Job mit Fortschritt.

Kein externer Crawl: music21 bringt die Choräle mit, exportiert sie als MusicXML und legt
je ein Werk (mit MusicXML-Datei) an. Idempotent: bereits vorhandene Titel werden übersprungen.
Schreibt über unqualifizierte SQL + storage.store_blob (erbt den Rollen-search_path wie die App).
"""
from __future__ import annotations

import hashlib
import os
import re


def run(conn, ctx) -> None:
    import music21 as m21
    from music21.musicxml.m21ToXml import GeneralObjectExporter

    from app.ingest import storage

    data_dir = os.environ.get("NOTEN_DATA_DIR", "/data")
    chorales = list(m21.corpus.chorales.Iterator())
    ctx.fortschritt(fertig=0, gesamt=len(chorales), aktuell="Bach-Choräle (music21)", log_zeile=f"{len(chorales)} Choräle im Corpus")
    neu = 0
    for i, ch in enumerate(chorales, 1):
        if ctx.abgebrochen():
            ctx.fortschritt(log_zeile="abgebrochen")
            return
        titel = None
        try:
            titel = (ch.metadata.title if ch.metadata else None) or f"Choral {i}"
            komp = "Johann Sebastian Bach"
            cur = conn.execute("select 1 from werk where titel = %s and komponist = %s limit 1", (titel, komp))
            if cur.fetchone():
                ctx.fortschritt(fertig=i, aktuell=titel)
                continue
            data = GeneralObjectExporter(ch).parse()  # MusicXML-Bytes
            data = re.sub(rb"<!DOCTYPE[^>]*>", b"", data, count=1)  # DOCTYPE strippen (defusedxml akzeptiert es dann)
            sha = hashlib.sha256(data).hexdigest()
            path = storage.store_blob(data_dir, sha, data)

            cur = conn.execute(
                "insert into werk (titel, komponist, gattung) values (%s,%s,'Choral') returning id", (titel, komp)
            )
            wid = cur.fetchone()["id"]
            cur = conn.execute("insert into fassung (werk_id) values (%s) returning id", (wid,))
            fid = cur.fetchone()["id"]
            cur = conn.execute(
                "insert into ausgabe (fassung_id, bevorzugt, rechtestatus) values (%s, true, 'public_domain') returning id",
                (fid,),
            )
            aid = cur.fetchone()["id"]
            conn.execute(
                """insert into datei (ausgabe_id, art, sha256, pfad, mime, groesse_bytes, original_name)
                   values (%s,'musicxml',%s,%s,'application/vnd.recordare.musicxml+xml',%s,%s)""",
                (aid, sha, str(path), len(data), titel[:180] + ".musicxml"),
            )
            neu += 1
        except Exception as exc:  # noqa: BLE001
            ctx.fortschritt(log_zeile=f"übersprungen {titel or i}: {exc}")
        ctx.fortschritt(fertig=i, aktuell=titel or f"#{i}")
    ctx.fortschritt(log_zeile=f"fertig — {neu} neue Werke")
