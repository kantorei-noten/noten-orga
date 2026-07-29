"""Backup-Konfiguration (nur Admin): Ziel, Aufbewahrung (wie viele), Uhrzeit (wann).

Die App (unprivilegiert) schreibt eine Config-Datei `<data_dir>/backup.conf`, die
`deploy/backup.sh` SICHER parst (grep + Validierung, kein `source`). Die Uhrzeit wird
über ein eng begrenztes sudo-Skript in den systemd-Timer übernommen — die App bekommt
keine weiteren Root-Rechte.
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth.deps import require_role
from ..config import get_settings

router = APIRouter(prefix="/backup", tags=["backup"])

_DEFAULT = {"ziel": "/var/backups/noten/repo", "keep_daily": 7, "keep_weekly": 4, "keep_monthly": 6, "uhrzeit": "03:30"}
_UHRZEIT = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_ZIEL = re.compile(r"^/[A-Za-z0-9._/-]{1,200}$")


def _conf_path() -> Path:
    return Path(get_settings().data_dir) / "backup.conf"


def _read() -> dict:
    cfg = dict(_DEFAULT)
    p = _conf_path()
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip().lower(), v.strip()
            if k == "ziel":
                cfg["ziel"] = v
            elif k == "uhrzeit":
                cfg["uhrzeit"] = v
            elif k in ("keep_daily", "keep_weekly", "keep_monthly"):
                try:
                    cfg[k] = int(v)
                except ValueError:
                    pass
    return cfg


def _write(cfg: dict) -> None:
    p = _conf_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "# Von der App verwaltet (Einstellungen → Backup). Wird von deploy/backup.sh sicher geparst.\n"
        f"ZIEL={cfg['ziel']}\n"
        f"KEEP_DAILY={cfg['keep_daily']}\n"
        f"KEEP_WEEKLY={cfg['keep_weekly']}\n"
        f"KEEP_MONTHLY={cfg['keep_monthly']}\n"
        f"UHRZEIT={cfg['uhrzeit']}\n",
        encoding="utf-8",
    )


class BackupConfig(BaseModel):
    ziel: str = Field(min_length=1, max_length=200)
    keep_daily: int = Field(ge=0, le=3650)
    keep_weekly: int = Field(ge=0, le=520)
    keep_monthly: int = Field(ge=0, le=240)
    uhrzeit: str = Field(min_length=4, max_length=5)


@router.get("/config")
async def get_config(user=Depends(require_role("admin"))):
    return _read()


@router.put("/config")
async def put_config(data: BackupConfig, user=Depends(require_role("admin"))):
    if not _UHRZEIT.match(data.uhrzeit):
        raise HTTPException(status_code=400, detail="Uhrzeit muss HH:MM sein (00:00–23:59)")
    if not _ZIEL.match(data.ziel):
        raise HTTPException(status_code=400, detail="Ziel muss ein absoluter Pfad sein (z. B. /var/backups/noten/repo)")
    cfg = data.model_dump()
    _write(cfg)
    # Der systemd-Pfad-Watcher (root) übernimmt die Uhrzeit in den Timer, sobald die
    # Config-Datei geschrieben wird — die App braucht dafür KEINE Rechte.
    return {**cfg, "hinweis": "Gespeichert. Ziel und Aufbewahrung gelten ab dem nächsten Backup, die Uhrzeit wird automatisch übernommen."}
