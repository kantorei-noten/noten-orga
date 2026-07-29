"""Isolierter Worker für music21-ChordPro auf NICHT vertrauenswürdiger MusicXML.

Läuft als EIGENER Prozess (RLIMIT_AS/CPU + Wall-Timeout setzt `app.ingest.sandbox`),
weil music21 MusicXML OHNE `defusedxml` parst: ein bösartiges/riesiges XML kann so
weder den API-Prozess crashen noch ihn per Speicher-/CPU-Bombe erschöpfen — der
Kindprozess wird durch die Limits gekillt, der API-Prozess bleibt unberührt.

MusicXML-Bytes kommen über stdin, Argumente (Titel, max. Silben) über argv,
das Ergebnis als JSON `{"text": …}` auf stdout. Importiert nur die schlanke
music21-ChordPro-Logik (app.catalog.chordgen_m21) — kein DB-/FastAPI-Code.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile


def main() -> int:
    op = sys.argv[1] if len(sys.argv) > 1 else ""
    if op != "chordpro":
        sys.stderr.write("unknown op\n")
        return 2
    titel = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "" else None
    max_silben = int(sys.argv[3]) if len(sys.argv) > 3 else 400
    data = sys.stdin.buffer.read()

    from app.catalog.chordgen_m21 import chordpro_aus_musicxml

    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".musicxml", delete=False) as fh:
            fh.write(data)
            tmp = fh.name
        text = chordpro_aus_musicxml(tmp, titel, max_silben)
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    sys.stdout.write(json.dumps({"text": text or ""}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
