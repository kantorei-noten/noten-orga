"""music21-basierte ChordPro-Erzeugung (Harmonieanalyse via chordify + Akkordsymbole).

Deutlich besser als der schlanke Eigen-Analyzer ([[chordgen]]), weil music21 echte
Akkordsymbole/Umkehrungen kennt. music21 ist NICHT in den App-Grunddeps (dep-Gruppe
`worker`) — dieses Modul wird nur benutzt, wenn `import music21` gelingt (Prod-venv
oder Worker-Image). Sonst greift der Fallback in `chordgen.chordpro_auto`.
"""
from __future__ import annotations

import bisect

_MAJKEY = {0: "C", 1: "G", 2: "D", 3: "A", 4: "E", 5: "B", 6: "F#", 7: "C#",
           -1: "F", -2: "Bb", -3: "Eb", -4: "Ab", -5: "Db", -6: "Gb", -7: "Cb"}


def chordpro_aus_musicxml(pfad: str, titel: str | None = None, max_silben: int = 400) -> str:
    """Erzeugt einen ChordPro-Vorschlag aus einer MusicXML-Datei mit music21."""
    import music21 as m21

    score = m21.converter.parse(pfad)
    parts = list(score.parts)
    if not parts:
        return ""

    def lyr_count(p) -> int:
        return sum(1 for n in p.recurse().notes if n.lyric)

    melody = max(parts, key=lyr_count)
    if lyr_count(melody) == 0:
        return ""

    # Akkorde je Zeitpunkt (chordify) + music21-Akkordsymbol
    chords = score.chordify().flatten()
    evs: list[tuple[float, str | None]] = []
    for c in chords.getElementsByClass("Chord"):
        fig = None
        try:
            f = m21.harmony.chordSymbolFigureFromChord(c)
            if f and "Identified" not in f and "Cannot" not in f:
                fig = f
        except Exception:
            fig = None
        evs.append((float(c.offset), fig))
    evs.sort(key=lambda x: x[0])
    offs = [o for o, _ in evs]

    key = None
    ks = score.recurse().getElementsByClass(m21.key.KeySignature)
    if ks:
        key = _MAJKEY.get(ks[0].sharps)

    zeilen: list[str] = []
    zeile: list[str] = []
    last_sym = None
    last_end = None
    n = 0
    for note in melody.flatten().notes:
        if not note.lyric:
            continue
        if n >= max_silben:
            break
        n += 1
        onset = float(note.offset)
        if last_end is not None and onset > last_end + 0.05 and zeile:
            zeilen.append(" ".join(zeile))
            zeile = []
            last_sym = None
        i = bisect.bisect_right(offs, onset) - 1
        fig = evs[i][1] if i >= 0 else None
        tok = ""
        if fig and fig != last_sym:
            tok = f"[{fig}]"
            last_sym = fig
        syl = note.lyrics[0].syllabic if note.lyrics else "single"
        wort = note.lyric + ("-" if syl in ("begin", "middle") else "")
        zeile.append(tok + wort)
        try:
            last_end = onset + float(note.duration.quarterLength)
        except Exception:
            last_end = onset
        if note.lyric[-1:] in ".!?;":
            zeilen.append(" ".join(zeile))
            zeile = []
            last_sym = None
    if zeile:
        zeilen.append(" ".join(zeile))

    kopf = []
    if titel:
        kopf.append(f"{{title: {titel}}}")
    if key:
        kopf.append(f"{{key: {key}}}")
    return "\n".join(kopf + ([""] if kopf else []) + zeilen).strip()
