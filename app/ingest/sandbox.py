"""Startet PyMuPDF-Operationen in einem isolierten Subprozess (Ressourcenlimits + Timeout).

Damit läuft das Parsen nicht vertrauenswürdiger PDFs NICHT mehr inline im API-Prozess:
- Ein Crash (Segfault in MuPDF) killt nur den Kindprozess.
- RLIMIT_CPU / RLIMIT_AS / RLIMIT_FSIZE + Wall-Timeout begrenzen Rechenzeit/Speicher/Ausgabe
  (Schutz gegen Dekompressionsbomben und Endlosschleifen).
Volle Netz-/Namespace-Isolation kommt in der Docker-Umgebung; hier zählen Crash- und
Ressourcen-Isolation.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys


class SandboxError(Exception):
    pass


def _preexec(mem_mb: int, cpu_s: int):
    import resource

    def apply():
        for res_id, soft in (
            (resource.RLIMIT_CPU, cpu_s),
            (resource.RLIMIT_AS, mem_mb * 1024 * 1024),
            (resource.RLIMIT_FSIZE, 256 * 1024 * 1024),
        ):
            try:
                resource.setrlimit(res_id, (soft, soft))
            except (ValueError, OSError):
                pass  # nicht überall setzbar (z. B. macOS) — best effort

    return apply


def run(op_args: list[str], data: bytes, settings, worker: str = "app.ingest.pdf_worker") -> dict:
    """Führt `python -m <worker> <op_args>` mit `data` auf stdin aus (RLIMIT + Timeout).

    Default-Worker ist der PDF-Worker; `worker=` wählt einen anderen isolierten Worker
    (z. B. `app.ingest.music21_worker` fürs music21-ChordPro auf nicht vertrauenswürdiger
    MusicXML)."""
    preexec = None
    if os.name == "posix":
        preexec = _preexec(settings.sandbox_mem_mb, settings.sandbox_cpu_seconds)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", worker, *op_args],
            input=data,
            capture_output=True,
            timeout=settings.sandbox_timeout_seconds,
            preexec_fn=preexec,
        )
    except subprocess.TimeoutExpired:
        raise SandboxError("timeout")
    except Exception as exc:  # Spawn fehlgeschlagen
        raise SandboxError(f"spawn: {exc}")
    if proc.returncode != 0:
        raise SandboxError(f"worker exit {proc.returncode}")
    try:
        return json.loads(proc.stdout.decode() or "{}")
    except Exception:
        raise SandboxError("bad output")
