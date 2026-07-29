"""Liedtext-Extraktion aus Notenblättern für die Gemeinde-Projektion.

Zwei Quellen:
- **PDF-Textebene** (Hauptquelle): Die Kantoreiarchiv-Scans sind Vektor-Engravings mit
  echter Textebene. Der Liedtext steht in normalen Text-Fonts, die Noten-Glyphen in einer
  Musik-Font (z. B. „AScore") und kommen als Zeichensalat heraus. Wir behalten nur wortartige
  Tokens (Buchstabenanteil je Span ≥ 45 %, Vokal im Token) und ziehen Silben zusammen.
- **MusicXML** (`<lyric><text>`), wo vorhanden — sauberer, mit Silben-Verbindung.

Das Ergebnis ist bewusst ein *Vorschlag*: Komponistennamen/Kopfzeilen/Wiederholungen können
durchrutschen. Der Nutzer putzt den Text in der Werk-Ansicht nach.
"""
from __future__ import annotations

import re

_VOWEL = re.compile(r"[aeiouyäöüàáâãäèéêëìíîïòóôõöùúûüAEIOUYÄÖÜ]")
_STRIP = ".,;:!?»«„“”\"'()[]*·—–-"

# Stimmen-/Instrumentenbezeichnungen und Vortragsangaben — keine Liedtexte
_LABELS = {
    "soprano", "sopran", "canto", "cantus", "descant", "alto", "altus", "alt",
    "tenore", "tenor", "basso", "bassus", "bass", "baß", "coro", "chorus", "choir",
    "tutti", "solo", "soli", "ripieno", "continuo", "organo", "organ", "orgel",
    "violino", "violine", "viola", "violoncello", "cello", "flauto", "flöte", "fagotto",
    "oboe", "clarinetto", "tromba", "corno", "timpani", "voce", "clavier", "cembalo",
    "score", "vocal", "contents", "editor", "edition",
}
_TEMPO = {
    "adagio", "allegro", "allegretto", "andante", "andantino", "largo", "larghetto",
    "presto", "vivace", "grave", "lento", "moderato", "maestoso", "cantabile",
    "cresc", "decresc", "dim", "forte", "fortissimo", "piano", "pianissimo", "mezzo",
    "dolce", "staccato", "legato", "ritard", "rall", "accel", "fine", "segno",
}

# an ein Wort geklebte Stimmen-Bezeichnung (z. B. "glorifiAlto", "beTenore") wieder abschneiden
_LABEL_SUFFIX = re.compile(
    r"(?<=[A-Za-zäöüß])"
    r"(Alt(?:o|us)?|Ten(?:ore|or)|Sopran(?:o)?|Cant(?:o|us)|Bass(?:o|us)?|Baß|"
    r"Coro|Chorus|Tutti|Solo|Soli|Ripieno|Continuo|Organo|Violino|Viola|Flauto|"
    r"Fagotto|Oboe|Tromba|Corno|Voce)$"
)


def _alpha_ratio(s: str) -> float:
    return sum(c.isalpha() for c in s) / max(1, len(s))


def _dehyphenate(text: str) -> str:
    """Silben-Bindestriche zusammenziehen: 'Ky- ri- e' -> 'Kyrie', 'al- - le' -> 'alle'."""
    out: list[str] = []
    join = False
    for t in text.split():
        if t in ("-", "–", "—"):  # allein stehender Melisma-Strich
            join = True
            continue
        ends = t[-1] in "-–—"
        core = t.rstrip("-–—")
        if join and out:
            out[-1] += core
        elif core:
            out.append(core)
        join = ends
    return " ".join(out)


def _keep_token(t: str) -> bool:
    c = t.strip(_STRIP).lower()
    if len(c) < 2 or c.isdigit() or c in _LABELS or c in _TEMPO:
        return False
    return bool(_VOWEL.search(c))


def _pdf_zeilen(pfad: str, settings, max_seiten: int) -> list[str]:
    """Font-gefilterte Text-Zeilen — bevorzugt im isolierten Subprozess (Crash-/Ressourcen-Schutz)."""
    if settings is not None and getattr(settings, "sandbox_enabled", True):
        from ..ingest.sandbox import SandboxError, run

        try:
            with open(pfad, "rb") as fh:
                data = fh.read()
            return list(run(["textlines", str(max_seiten)], data, settings).get("lines", []))
        except SandboxError:
            return []
    # Inline-Fallback (sandbox_enabled=False)
    import pymupdf

    doc = pymupdf.open(pfad)
    zeilen: list[str] = []
    for i in range(min(max_seiten, doc.page_count)):
        for block in doc[i].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spantext = " ".join(
                    s["text"] for s in line.get("spans", []) if _alpha_ratio(s["text"]) >= 0.45
                )
                if spantext.strip():
                    zeilen.append(spantext)
    doc.close()
    return zeilen


def liedtext_aus_pdf(pfad: str, settings=None, max_seiten: int = 8) -> str:
    """Liedtext aus der PDF-Textebene, Noten-Glyphen und Kopfzeilen herausgefiltert."""
    zeilen: list[str] = []
    for spantext in _pdf_zeilen(pfad, settings, max_seiten):
        low = spantext.lower()
        if any(j in low for j in ("www.", "http", "kantoreiarchiv", "kreuznacher")):
            continue
        if re.search(r"\bp\.?\s*\d", low):  # Seitenmarken "p. 1"
            continue
        zeilen.append(spantext)
    text = _dehyphenate(" ".join(zeilen))
    toks = [_LABEL_SUFFIX.sub("", t) for t in text.split()]
    toks = [t for t in toks if _keep_token(t)]
    return " ".join(toks).strip()


def liedtext_aus_musicxml(pfad: str) -> str:
    """Liedtext aus MusicXML-<lyric>-Elementen (längste Strophe), Silben verbunden."""
    try:
        from defusedxml import ElementTree as ET

        root = ET.parse(pfad).getroot()
    except Exception:
        return ""

    def local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    strophen: dict[str, list[tuple[str, str]]] = {}
    for el in root.iter():
        if local(el.tag) != "lyric":
            continue
        num = el.get("number", "1")
        syl, txt = "single", None
        for ch in el:
            lt = local(ch.tag)
            if lt == "syllabic":
                syl = ch.text or "single"
            elif lt == "text":
                txt = ch.text
        if txt:
            strophen.setdefault(num, []).append((syl, txt))

    best = ""
    for items in strophen.values():
        parts: list[str] = []
        prev = "single"
        for syl, txt in items:
            if parts and prev in ("begin", "middle"):
                parts[-1] += txt
            else:
                parts.append(txt)
            prev = syl
        s = " ".join(parts).strip()
        if len(s) > len(best):
            best = s
    return best


def beste_extraktion(dateien: list[tuple[str, str]], settings=None, max_dateien: int = 15) -> str:
    """Aus allen Werk-Dateien (Pfad, Art) den besten Liedtext wählen.

    MusicXML mit brauchbarem Text wird bevorzugt (sauberer); sonst die PDF-Stimme
    mit dem meisten Text (typischerweise eine Vokalstimme, nicht eine Instrumentalstimme).
    """
    mxml = [p for p, a in dateien if a == "musicxml"][:max_dateien]
    pdfs = [p for p, a in dateien if a in ("scan_pdf", "import_pdf")][:max_dateien]

    best_x = ""
    for p in mxml:
        t = liedtext_aus_musicxml(p)
        if len(t.split()) > len(best_x.split()):
            best_x = t
    if len(best_x.split()) >= 20:
        return best_x

    best_p = ""
    for p in pdfs:
        try:
            t = liedtext_aus_pdf(p, settings)
        except Exception:
            continue
        if len(t.split()) > len(best_p.split()):
            best_p = t
            if len(best_p.split()) >= 250:  # genug für eine Folienreihe
                break
    return best_p or best_x
