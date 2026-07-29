"""Sichere MusicXML-/.mxl-Verarbeitung (Grundlage für Verovio-Veredelung).

Alle Fremd-XML ausschließlich über defusedxml (XXE-Schutz); .mxl (ZIP) mit
Entry-/Größen-/Ratio-Limits und Zip-Slip-Schutz.
"""
from __future__ import annotations

import io
import zipfile

import defusedxml.ElementTree as DET
from defusedxml.common import DefusedXmlException

from ..ingest.validation import ValidationError

MAX_ENTRIES = 200
MAX_TOTAL = 50 * 1024 * 1024
MAX_RATIO = 200
MUSICXML_ROOTS = {"score-partwise", "score-timewise"}


def _validate_xml(text: str) -> None:
    try:
        root = DET.fromstring(text.encode("utf-8"))
    except DefusedXmlException:
        raise ValidationError("xml_unsafe", "MusicXML mit unsicheren Konstrukten abgelehnt")
    except Exception:
        raise ValidationError("xml_invalid", "MusicXML nicht wohlgeformt")
    if root.tag.split("}")[-1] not in MUSICXML_ROOTS:
        raise ValidationError("not_musicxml", "Kein MusicXML-Dokument")


def _rootfile_from_container(zf: zipfile.ZipFile) -> str | None:
    if "META-INF/container.xml" not in zf.namelist():
        return None
    try:
        root = DET.fromstring(zf.read("META-INF/container.xml"))
    except Exception:
        return None
    for el in root.iter():
        if el.tag.split("}")[-1] == "rootfile":
            return el.get("full-path")
    return None


def extract_musicxml(data: bytes) -> str:
    """Liefert den validierten MusicXML-Text aus .xml/.musicxml oder .mxl (ZIP)."""
    head = data.lstrip()[:64]
    if head.startswith(b"<?xml") or head.startswith(b"<"):
        text = data.decode("utf-8", errors="replace")
        _validate_xml(text)
        return text

    if data[:4] not in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
        raise ValidationError("not_musicxml", "Kein MusicXML/MXL")

    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        infos = zf.infolist()
    except Exception:
        raise ValidationError("bad_zip", "MXL/ZIP nicht lesbar")

    if len(infos) > MAX_ENTRIES:
        raise ValidationError("zip_bomb", "Archiv hat zu viele Einträge")
    total = sum(i.file_size for i in infos)
    comp = sum(i.compress_size for i in infos) or 1
    if total > MAX_TOTAL or total / comp > MAX_RATIO:
        raise ValidationError("zip_bomb", "Archiv entpackt zu groß / verdächtiges Verhältnis")

    names = zf.namelist()
    target = _rootfile_from_container(zf)
    if not target:
        target = next(
            (n for n in names if n.lower().endswith((".xml", ".musicxml")) and not n.startswith("META-INF")),
            None,
        )
    if not target or target not in names:
        raise ValidationError("not_musicxml", "MusicXML im Archiv nicht gefunden")
    # Zip-Slip: keine absoluten/aufsteigenden Pfade akzeptieren
    if target.startswith("/") or ".." in target.replace("\\", "/").split("/"):
        raise ValidationError("zip_slip", "Ungültiger Pfad im Archiv")

    xml = zf.read(target).decode("utf-8", errors="replace")
    _validate_xml(xml)
    return xml
