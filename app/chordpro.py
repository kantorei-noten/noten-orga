"""ChordPro-Transposition: Akkorde in [ ] um n Halbtöne verschieben.

Nur echte Akkorde werden transponiert — Abschnittsmarken wie [Chorus] bleiben."""
from __future__ import annotations

import re

_SCALE = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_INDEX = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "Fb": 4, "E#": 5,
    "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10,
    "B": 11, "Cb": 11, "B#": 0,
}

# Akkord = Grundton (A-G, optional #/b) + optionaler Suffix + optionaler Bass (/x)
_CHORD = re.compile(
    r"^[A-G][#b]?(?:(?:[mM]|maj|min|dim|aug|sus|add|[0-9°+])[0-9A-Za-z#b()+\-]*)?(?:/[A-G][#b]?)?$"
)


def _shift(note: str, n: int) -> str:
    if note not in _INDEX:
        return note
    return _SCALE[(_INDEX[note] + n) % 12]


def _transpose_chord(token: str, n: int) -> str:
    if not _CHORD.match(token):
        return token  # keine echte Akkordangabe (z. B. [Chorus])
    bass = None
    body = token
    if "/" in body:
        body, bass = body.rsplit("/", 1)
    m = re.match(r"^([A-G][#b]?)(.*)$", body)
    if not m:
        return token
    result = _shift(m.group(1), n) + m.group(2)
    if bass is not None:
        result += "/" + _shift(bass, n)
    return result


def transponiere(text: str, halbtoene: int) -> str:
    n = halbtoene % 12  # +12 bzw. -12 = identisch
    if n == 0:
        return text
    return re.sub(r"\[([^\]]+)\]", lambda mm: "[" + _transpose_chord(mm.group(1), n) + "]", text)
