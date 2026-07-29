# Fremdkomponenten und ihre Lizenzen

Kantorei steht unter **AGPL-3.0-or-later** (siehe [`LICENSE`](LICENSE)). Diese Wahl ist keine
Geschmacksfrage: **PyMuPDF** (PDF-Verarbeitung) ist AGPL-3.0 lizenziert, **psycopg 3** und
**Verovio** sind LGPL-3.0. Eine freizügigere Lizenz (MIT/BSD) wäre für dieses Gesamtwerk
nicht zulässig, ohne PyMuPDF zu ersetzen.

## Backend (Python)

| Paket | Lizenz | Rolle |
|---|---|---|
| PyMuPDF | **AGPL-3.0** (dual, kommerziell von Artifex) | PDF lesen, Seiten zählen, Vorschaubilder |
| psycopg 3 | **LGPL-3.0-only** | PostgreSQL-Treiber |
| FastAPI | MIT | Web-Framework |
| uvicorn | BSD-3-Clause | ASGI-Server |
| pydantic-settings | MIT | Konfiguration aus Umgebungsvariablen |
| Alembic | MIT | Datenbank-Migrationen |
| argon2-cffi | MIT | Passwort-Hashing (Argon2id) |
| pyotp | MIT | TOTP / Zwei-Faktor |
| Pillow | MIT-CMU | Bildverarbeitung, Vorschaubilder |
| python-multipart | Apache-2.0 | Datei-Uploads |
| defusedxml | PSF | XML-Parsing ohne XXE/Entity-Angriffe |
| music21 (nur Worker-Image) | BSD-3-Clause | Harmonieanalyse, MusicXML |

## Frontend (npm)

| Paket | Lizenz | Rolle |
|---|---|---|
| Verovio | **LGPL-3.0-or-later** | MusicXML/MEI als Notenbild rendern, transponieren |
| pdf.js (`pdfjs-dist`) | Apache-2.0 | PDF-Anzeige im Browser |
| Vue 3, vue-router, Pinia | MIT | PWA-Oberfläche |
| Vite, `@vitejs/plugin-vue`, vite-plugin-pwa | MIT | Build und Service-Worker |

## Container-Basis

| Image | Lizenz |
|---|---|
| `postgres:17-alpine` | PostgreSQL License |
| `caddy:2-alpine` | Apache-2.0 |
| `python:3.13-slim` | PSF (Python) + Debian-Pakete unter ihren jeweiligen Lizenzen |
| `node:22-slim` (nur Build-Stufe) | MIT (Node.js) + Debian-Pakete |

## Hinweise zu LGPL-Komponenten

Verovio und psycopg sind LGPL: Sie werden **unverändert** eingebunden (Verovio als
WASM-Bundle über npm, psycopg als installiertes Wheel). Wer sie austauschen möchte, kann das
tun — der Build ist über `web/package.json` bzw. `pyproject.toml` und `uv.lock` vollständig
nachvollziehbar.

Die Lizenztexte der Fremdkomponenten liegen jeweils in deren Paketen
(`.venv/lib/…/*.dist-info/` bzw. `web/node_modules/<paket>/LICENSE`).

Diese Übersicht wurde aus den installierten Paket-Metadaten erzeugt und nennt die direkten
Abhängigkeiten. Transitive Abhängigkeiten sind in `uv.lock` und `web/package-lock.json`
vollständig festgehalten.
