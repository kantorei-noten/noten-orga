"""Optionaler ClamAV-Scan (INSTREAM) hochgeladener Dateien.

Aus, solange `clamav_socket` nicht gesetzt ist (Default) — dann No-op, keine Abhängigkeit,
kein laufender Daemon nötig. In der Docker-Umgebung per `NOTEN_CLAMAV_SOCKET` aktivierbar
(z. B. 'unix:/run/clamav/clamd.ctl' oder 'tcp:127.0.0.1:3310'). Ist der Scanner konfiguriert,
aber nicht erreichbar, wird fail-closed abgelehnt (lieber blocken als ungescannt speichern).
"""
from __future__ import annotations

import socket
import struct

from .validation import ValidationError


def _connect(spec: str) -> socket.socket:
    if spec.startswith("unix:"):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(30)
        s.connect(spec[len("unix:"):])
    elif spec.startswith("tcp:"):
        host, port = spec[len("tcp:"):].rsplit(":", 1)
        s = socket.create_connection((host, int(port)), timeout=15)
        s.settimeout(30)
    else:
        raise ValueError("clamav_socket muss mit 'unix:' oder 'tcp:' beginnen")
    return s


def scan(data: bytes, settings) -> None:
    """Wirft ValidationError, wenn ClamAV etwas findet oder nicht erreichbar ist. No-op ohne Konfiguration."""
    spec = getattr(settings, "clamav_socket", None)
    if not spec:
        return
    try:
        s = _connect(spec)
    except Exception:
        raise ValidationError("scanner_unavailable", "Virenscanner nicht erreichbar — Upload abgelehnt")
    try:
        s.sendall(b"zINSTREAM\x00")
        view = memoryview(data)
        for i in range(0, len(data), 65536):
            chunk = view[i : i + 65536]
            s.sendall(struct.pack("!I", len(chunk)) + bytes(chunk))
        s.sendall(struct.pack("!I", 0))  # Ende
        resp = b""
        while b"\x00" not in resp:
            part = s.recv(4096)
            if not part:
                break
            resp += part
    except Exception:
        raise ValidationError("scan_error", "Virenscan fehlgeschlagen — Upload abgelehnt")
    finally:
        s.close()
    text = resp.decode("utf-8", "replace")
    if "FOUND" in text:
        raise ValidationError("virus", "Datei von ClamAV abgelehnt (Schadsoftware erkannt)")
    if "OK" not in text:
        raise ValidationError("scan_error", "Virenscan fehlgeschlagen — Upload abgelehnt")
