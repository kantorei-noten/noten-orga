"""Konfiguration — ausschließlich aus Umgebungsvariablen (Präfix NOTEN_) bzw. .env.

Secrets kommen im Betrieb aus Docker-Secrets/_FILE bzw. /opt/noten/secrets/noten.env,
niemals aus dem Git-Repo (s. CLAUDE.md, Sicherheit).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NOTEN_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Datenbank (lokal: isolierter .devdb-Cluster auf Port 5433)
    database_url: str = "postgresql://noten_app:devpw@localhost:5433/noten"

    # dev | test | prod
    environment: str = "dev"

    # Sitzungs-/Signatur-Geheimnis — im Betrieb zwingend überschreiben
    session_secret: str = "dev-insecure-change-me"

    log_level: str = "INFO"

    # Objektspeicher (Uploads) — außerhalb des Web-Roots
    data_dir: Path = Path("var/data")

    # --- Upload-Limits (harte Grenzen gegen bösartige Dateien) ---
    max_upload_bytes: int = 50 * 1024 * 1024  # 50 MB
    max_pdf_pages: int = 400
    thumb_max_px: int = 1400  # längste Kante der Vorschau
    max_image_pixels: int = 64_000_000  # Pillow-Schutz gegen Dekompressionsbomben

    # --- Härtung: Fremddatei-Parsen isolieren ---
    sandbox_enabled: bool = True  # PyMuPDF-Parsen in eigenem Prozess (Crash-/Ressourcen-Isolation)
    sandbox_mem_mb: int = 2048  # RLIMIT_AS des Workers
    sandbox_cpu_seconds: int = 25  # RLIMIT_CPU des Workers
    sandbox_timeout_seconds: int = 40  # Wall-Clock-Timeout des Workers
    # ClamAV-Scan (aus per Default). Z. B. 'unix:/run/clamav/clamd.ctl' oder 'tcp:127.0.0.1:3310'
    clamav_socket: str | None = None

    # --- Auth / Sessions ---
    session_cookie_name: str = "noten_session"
    session_ttl_seconds: int = 60 * 60 * 12  # 12 h
    secure_cookies: bool = False  # im Betrieb (HTTPS) auf True
    max_login_attempts: int = 5
    lockout_minutes: int = 15
    totp_valid_window: int = 1  # ±30 s Toleranz
    totp_issuer: str = "Kantorei"
    totp_pflicht: bool = True  # Demo: per NOTEN_TOTP_PFLICHT=false abschaltbar (nur Passwort)

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()
