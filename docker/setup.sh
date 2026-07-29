#!/usr/bin/env bash
# Erstellt docker/.env mit sicher erzeugten Zufallswerten. Läuft einmal vor dem ersten Start.
#
#   cd docker && ./setup.sh && docker compose up -d
#
# Eine vorhandene .env wird NICHT überschrieben.
set -euo pipefail
cd "$(dirname "$0")"

ENV_DATEI=.env

if [ -f "$ENV_DATEI" ]; then
  echo "» $ENV_DATEI existiert bereits — es wird nichts geändert."
  echo "  (Zum Neuanlegen die Datei vorher wegsichern und löschen.)"
  exit 0
fi

zufall() {  # $1 = Anzahl Bytes
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$1"
  else
    head -c "$1" /dev/urandom | od -An -tx1 | tr -d ' \n'
  fi
}

DB_PASS="$(zufall 24)"
SESSION_SECRET="$(zufall 32)"

DOMAIN="${NOTEN_DOMAIN:-}"
if [ -z "$DOMAIN" ] && [ -t 0 ]; then
  echo
  echo "Öffentliche Domain für diese Installation (z. B. noten.example.org)."
  echo "Caddy holt dafür automatisch ein Let's-Encrypt-Zertifikat."
  echo "Leer lassen für lokalen Betrieb auf http://localhost — dann ohne HTTPS."
  printf "Domain [leer]: "
  read -r DOMAIN || DOMAIN=""
fi

# Ohne HTTPS können die Sitzungs-Cookies nicht auf "secure" stehen, sonst ist kein Login möglich.
if [ -n "$DOMAIN" ]; then SECURE=true; else SECURE=false; fi

umask 077
cat > "$ENV_DATEI" <<EOF
# Von setup.sh erzeugt — enthält Geheimnisse. Nicht ins Git, nicht weitergeben.

# --- Geheimnisse (zufällig erzeugt) ---
NOTEN_DB_PASSWORD=$DB_PASS
NOTEN_SESSION_SECRET=$SESSION_SECRET

# --- Erreichbarkeit ---
# Domain -> Caddy holt automatisch ein Let's-Encrypt-Zertifikat. Leer = http auf :80.
NOTEN_DOMAIN=$DOMAIN
# Sitzungs-Cookies nur über HTTPS senden (bei Betrieb ohne TLS zwingend false).
NOTEN_SECURE_COOKIES=$SECURE
# Host-Ports, falls 80/443 schon belegt sind (z. B. auf einem NAS).
# NOTEN_HTTP_PORT=8090
# NOTEN_HTTPS_PORT=8453

# --- Version der Images (ein Tag wie v1.0.0 friert den Stand ein) ---
NOTEN_VERSION=latest

# --- Zwei-Faktor ---
# Pflicht-2FA für alle Konten. Nur zum Ausprobieren auf false setzen.
NOTEN_TOTP_PFLICHT=true

# --- Sicherung ---
# Zielverzeichnis: Host-Pfad (empfohlen, z. B. /mnt/backup/kantorei) oder das
# Docker-Volume "backups" als Standard.
NOTEN_BACKUP_DIR=backups
NOTEN_BACKUP_UHRZEIT=03:30
NOTEN_BACKUP_KEEP_DAYS=14
# Zeitzone für die Sicherungs-Uhrzeit (ohne sie läuft sie nach UTC).
TZ=${TZ:-Europe/Berlin}
EOF
chmod 600 "$ENV_DATEI"

echo
echo "✓ $ENV_DATEI angelegt (Rechte 600), Passwörter zufällig erzeugt."
if [ -n "$DOMAIN" ]; then
  echo "  Domain: $DOMAIN — der A-Record muss auf diesen Server zeigen, sonst gibt es kein Zertifikat."
else
  echo "  Ohne Domain: erreichbar über http://localhost (kein HTTPS, Cookies ungesichert)."
fi
echo
echo "Weiter mit:"
echo "  docker compose up -d"
echo "  docker compose exec app python -m app.cli create-admin <benutzername>"
