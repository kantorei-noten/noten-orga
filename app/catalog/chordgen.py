"""ChordPro aus MusicXML erzeugen — Akkorde aus der Vertikale ableiten (ohne music21).

Fast keine Datei im Bestand hat fertige Akkordsymbole (<harmony>), aber ~78 % haben Text.
Also leiten wir die Akkorde selbst ab: MusicXML defensiv mit defusedxml parsen (XXE-sicher),
den zeitlichen Verlauf aller Stimmen rekonstruieren und an jeder Melodie-Silbe die klingenden
Tonhöhen zu einem Akkordsymbol zusammenfassen. Zielrepertoire: homophone Choräle/Lieder.
Das Ergebnis ist ein *Vorschlag* zum Nachputzen im ChordPro-Editor.
"""
from __future__ import annotations

_STEP = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_ROOTNAME = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
_MAJKEY = {0: "C", 1: "G", 2: "D", 3: "A", 4: "E", 5: "B", 6: "F#", 7: "C#",
           -1: "F", -2: "Bb", -3: "Eb", -4: "Ab", -5: "Db", -6: "Gb", -7: "Cb"}

# Akkord-Vorlagen (Intervalle über dem Grundton) + Komplexitätskosten
# (Dreiklänge sind „billig" → werden bevorzugt; exotische Akkorde teuer → nur wenn nötig).
_TEMPLATES = [
    ("", (0, 4, 7), 0.0),
    ("m", (0, 3, 7), 0.0),
    ("dim", (0, 3, 6), 0.7),
    ("aug", (0, 4, 8), 1.6),
    ("7", (0, 4, 7, 10), 1.0),
    ("m7", (0, 3, 7, 10), 1.2),
    ("maj7", (0, 4, 7, 11), 1.6),
    ("sus4", (0, 5, 7), 1.3),
    ("sus2", (0, 2, 7), 1.3),
    ("m7b5", (0, 3, 6, 10), 2.4),
    ("dim7", (0, 3, 6, 9), 2.4),
]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find(el, name):
    for c in el:
        if _local(c.tag) == name:
            return c
    return None


def _iter(el, name):
    return [c for c in el if _local(c.tag) == name]


def _parse(path: str):
    """MusicXML → (alle Klang-Events, Melodie-Silben, Tonart-fifths)."""
    from defusedxml import ElementTree as ET

    root = ET.parse(path).getroot()
    all_events: list[tuple[float, float, int]] = []  # (onset, dauer, midi) in Vierteln
    melodien: list[list[tuple]] = []  # je Stimme: (onset, dauer, midi|None, text, syllabic)
    fifths = 0

    for part in _iter(root, "part"):
        divisions = 1
        measure_start = 0.0
        last_dur = 0.0
        pevents: list[tuple] = []
        for measure in _iter(part, "measure"):
            cursor = 0.0
            maxcur = 0.0
            for el in measure:
                t = _local(el.tag)
                if t == "attributes":
                    d = _find(el, "divisions")
                    if d is not None and d.text:
                        divisions = int(d.text)
                    key = _find(el, "key")
                    if key is not None:
                        ff = _find(key, "fifths")
                        if ff is not None and ff.text:
                            fifths = int(ff.text)
                elif t == "backup":
                    dd = _find(el, "duration")
                    if dd is not None and dd.text:
                        cursor -= int(dd.text) / divisions
                elif t == "forward":
                    dd = _find(el, "duration")
                    if dd is not None and dd.text:
                        cursor += int(dd.text) / divisions
                        maxcur = max(maxcur, cursor)
                elif t == "note":
                    is_chord = _find(el, "chord") is not None
                    is_grace = _find(el, "grace") is not None
                    is_rest = _find(el, "rest") is not None
                    durel = _find(el, "duration")
                    dur = (int(durel.text) / divisions) if (durel is not None and durel.text) else 0.0
                    if is_grace:
                        dur = 0.0
                    onset = measure_start + (cursor - last_dur if is_chord else cursor)
                    midi = None
                    if not is_rest:
                        p = _find(el, "pitch")
                        if p is not None:
                            step = _find(p, "step")
                            alt = _find(p, "alter")
                            octv = _find(p, "octave")
                            pc = _STEP.get(step.text if step is not None else "C", 0)
                            if alt is not None and alt.text:
                                pc += int(alt.text)
                            if octv is not None and octv.text:
                                midi = pc + 12 * (int(octv.text) + 1)
                    if midi is not None and dur > 0:
                        all_events.append((onset, dur, midi))
                    lyr = _find(el, "lyric")
                    if lyr is not None and not is_rest and midi is not None:
                        txt = _find(lyr, "text")
                        syl = _find(lyr, "syllabic")
                        if txt is not None and txt.text:
                            pevents.append((onset, dur, midi, txt.text, syl.text if syl is not None else "single"))
                    if not is_chord and not is_grace:
                        cursor += dur
                        last_dur = dur
                        maxcur = max(maxcur, cursor)
            measure_start += maxcur if maxcur > 0 else cursor
        if pevents:
            melodien.append(pevents)

    melody = max(melodien, key=len) if melodien else []
    return all_events, melody, fifths


def _identify(midis: list[int]) -> str | None:
    """Tonhöhen → Akkordsymbol (Umkehrungen ignoriert; Grundton = Bass bevorzugt)."""
    if not midis:
        return None
    pcs = {m % 12 for m in midis}
    if len(pcs) < 2:
        return None
    bass = min(midis) % 12
    best = None
    best_cost = 1e9
    for root in range(12):
        for name, ivals, komplex in _TEMPLATES:
            tmpl = {(root + i) % 12 for i in ivals}
            if not tmpl <= pcs:
                continue
            extra = len(pcs - tmpl)  # klingende Töne, die der Akkord nicht erklärt (Durchgangstöne)
            # Kosten: nicht erklärte Töne + Akkord-Komplexität; Grundton==Bass wird belohnt
            cost = 0.6 * extra + komplex - (0.5 if root == bass else 0.0)
            if cost < best_cost - 1e-9:
                best_cost = cost
                best = (root, name)
    if best is None:
        # Notlösung: Bass als Grundton, Terz bestimmt Dur/Moll
        if (bass + 4) % 12 in pcs:
            return _ROOTNAME[bass]
        if (bass + 3) % 12 in pcs:
            return _ROOTNAME[bass] + "m"
        return None
    root, name = best
    return _ROOTNAME[root] + name


def chordpro_aus_musicxml(path: str, titel: str | None = None, max_silben: int = 400) -> str:
    """Erzeugt einen ChordPro-Vorschlag (Direktiven + [Akkord]Silbe) aus einer MusicXML-Datei."""
    try:
        all_events, melody, fifths = _parse(path)
    except Exception:
        return ""
    if not melody:
        return ""
    all_events.sort()

    zeilen: list[str] = []
    zeile: list[str] = []
    last_sym = None
    last_end = None
    n = 0
    for onset, dur, midi, text, syl in melody:
        if n >= max_silben:
            break
        n += 1
        # Phrasen-Umbruch: Pause (Lücke) vor dieser Silbe → neue Zeile
        if last_end is not None and onset > last_end + 0.05 and zeile:
            zeilen.append(" ".join(zeile))
            zeile = []
            last_sym = None
        sounding = [mm for (o, d, mm) in all_events if o <= onset + 1e-6 < o + d]
        sounding.append(midi)
        sym = _identify(sounding)
        tok = ""
        if sym and sym != last_sym:
            tok = f"[{sym}]"
            last_sym = sym
        wort = text + ("-" if syl in ("begin", "middle") else "")
        zeile.append(tok + wort)
        last_end = onset + dur
        # Satzzeichen → weicher Zeilenumbruch
        if text[-1:] in ".!?;":
            zeilen.append(" ".join(zeile))
            zeile = []
            last_sym = None
    if zeile:
        zeilen.append(" ".join(zeile))

    kopf = []
    if titel:
        kopf.append(f"{{title: {titel}}}")
    if fifths in _MAJKEY:
        kopf.append(f"{{key: {_MAJKEY[fifths]}}}")
    return "\n".join(kopf + ([""] if kopf else []) + zeilen).strip()


def music21_verfuegbar() -> bool:
    """True, wenn music21 installiert ist — geprüft via find_spec, OHNE music21 in
    diesen Prozess zu importieren (das eigentliche Parsen läuft isoliert im Sandbox-
    Subprozess, s. app/ingest/music21_worker.py)."""
    import importlib.util

    return importlib.util.find_spec("music21") is not None


def chordpro_auto(path: str, titel: str | None = None, max_silben: int = 400) -> tuple[str, str]:
    """ChordPro erzeugen und dabei die beste verfügbare Engine wählen.

    Nutzt music21 (Harmonieanalyse), *wenn installiert* — sonst den schlanken
    Eigen-Analyzer. Fällt bei jedem music21-Fehler/leerem Ergebnis sauber auf den
    Eigenbau zurück. Rückgabe: (chordpro_text, engine) mit engine ∈ {"music21","basis"}.
    """
    if music21_verfuegbar():
        try:
            from . import chordgen_m21

            t = chordgen_m21.chordpro_aus_musicxml(path, titel, max_silben)
            if t and t.strip():
                return t, "music21"
        except Exception:
            pass  # defensiv: bei jedem music21-Problem den Eigenbau nehmen
    return chordpro_aus_musicxml(path, titel, max_silben), "basis"
