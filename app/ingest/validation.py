"""Defensive Validierung hochgeladener Fremddateien.

Grundsatz (CLAUDE.md): Uploads sind NIE vertrauenswürdig. Der Dateityp wird
per Magic-Byte erkannt (nicht per Client-MIME), strukturell geprüft und gegen
harte Grenzen abgeglichen. XML ausschließlich über defusedxml (XXE-Schutz).
"""
from __future__ import annotations

import io
import zipfile

MUSICXML_ROOTS = {"score-partwise", "score-timewise"}

# Aktive PDF-Inhalte, die in Notenblättern nichts verloren haben (Defense-in-depth,
# ergänzend zur Sandbox/ClamAV). Best-effort auf Rohbytes: fängt unkomprimierte Fälle.
_PDF_DANGER = (b"/JavaScript", b"/Launch", b"/EmbeddedFile", b"/RichMedia", b"/XFA", b"/OpenAction", b"/AA")


class ValidationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _sniff(data: bytes) -> str | None:
    """Erkennt den Typ anhand der Signatur — unabhängig vom behaupteten MIME."""
    if data[:5] == b"%PDF-":
        return "pdf"
    if data[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
        return "zip"  # .mxl = ZIP
    head = data.lstrip()[:256]
    if head.startswith(b"<?xml") or head.startswith(b"<"):
        return "xml"
    return None


def validate(data: bytes, settings) -> tuple[str, str, int | None]:
    """Gibt (kind, mime, seiten) zurück oder wirft ValidationError."""
    if not data:
        raise ValidationError("empty", "Leere Datei")
    if len(data) > settings.max_upload_bytes:
        raise ValidationError("too_large", "Datei überschreitet das Größenlimit")
    kind = _sniff(data)
    if kind == "pdf":
        return _validate_pdf(data, settings)
    if kind == "xml":
        return _validate_musicxml(data)
    if kind == "zip":
        return _validate_mxl(data, settings)
    raise ValidationError("unsupported", "Dateityp nicht erlaubt (nur PDF, MusicXML, MXL)")


def _pdf_pages(data: bytes, settings) -> int:
    """Seitenzahl ermitteln — bevorzugt im isolierten Subprozess (Crash-/Ressourcen-Schutz)."""
    if getattr(settings, "sandbox_enabled", True):
        from .sandbox import SandboxError, run

        try:
            return int(run(["pages"], data, settings).get("pages", 0))
        except SandboxError:
            raise ValidationError("corrupt_pdf", "PDF nicht lesbar")
    import pymupdf

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
        n = doc.page_count
        doc.close()
        return n
    except Exception:
        raise ValidationError("corrupt_pdf", "PDF nicht lesbar")


def _validate_pdf(data: bytes, settings) -> tuple[str, str, int]:
    for token in _PDF_DANGER:
        if token in data:
            raise ValidationError("pdf_active_content", "PDF mit aktivem Inhalt (Skript/Aktion) abgelehnt")
    pages = _pdf_pages(data, settings)
    if pages < 1:
        raise ValidationError("corrupt_pdf", "PDF ohne Seiten")
    if pages > settings.max_pdf_pages:
        raise ValidationError("too_many_pages", "PDF hat zu viele Seiten")
    return "pdf", "application/pdf", pages


def _validate_musicxml(data: bytes) -> tuple[str, str, None]:
    import defusedxml.ElementTree as DET
    from defusedxml.common import DefusedXmlException

    try:
        root = DET.fromstring(data)
    except DefusedXmlException:
        # XXE / Entity-Expansion / externe Referenz
        raise ValidationError("xml_unsafe", "XML mit unsicheren Konstrukten abgelehnt")
    except Exception:
        raise ValidationError("xml_invalid", "XML nicht wohlgeformt")
    tag = root.tag.split("}")[-1]
    if tag not in MUSICXML_ROOTS:
        raise ValidationError("not_musicxml", "Kein MusicXML-Dokument")
    return "xml", "application/vnd.recordare.musicxml+xml", None


def _validate_mxl(data: bytes, settings) -> tuple[str, str, None]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        infos = zf.infolist()
    except Exception:
        raise ValidationError("bad_zip", "MXL/ZIP nicht lesbar")
    if len(infos) > 200:
        raise ValidationError("zip_bomb", "Archiv hat zu viele Einträge")
    if sum(i.file_size for i in infos) > settings.max_upload_bytes * 20:
        raise ValidationError("zip_bomb", "Archiv entpackt zu groß")
    return "zip", "application/vnd.recordare.musicxml", None
