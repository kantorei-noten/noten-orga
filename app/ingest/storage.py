"""Content-addressed Blob-Speicher: Ablage außerhalb des Web-Roots, per SHA-256."""
from __future__ import annotations

import re
from pathlib import Path


def blob_path(data_dir: Path, sha256: str) -> Path:
    return Path(data_dir) / "blobs" / sha256[:2] / sha256


def thumb_path(data_dir: Path, datei_id) -> Path:
    return Path(data_dir) / "thumbs" / f"{datei_id}.webp"


def store_blob(data_dir: Path, sha256: str, data: bytes) -> Path:
    """Schreibt den Blob (falls noch nicht vorhanden) und gibt den Pfad zurück."""
    target = blob_path(data_dir, sha256)
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(target)  # atomisch
    return target


_SAFE = re.compile(r"[^A-Za-z0-9._ äöüÄÖÜß-]+")


def sanitize_filename(name: str | None) -> str | None:
    """Nur der Basisname, ohne Pfadanteile/Steuerzeichen, längenbegrenzt."""
    if not name:
        return None
    name = name.replace("\\", "/").split("/")[-1]
    name = _SAFE.sub("_", name).strip()
    return name[:200] or None
