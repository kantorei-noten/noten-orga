#!/bin/sh
# Nächtliche Sicherung für den Docker-Stack: Datenbank (pg_dump) + Objektspeicher (/data).
#
#   backup.sh daemon   — Endlosschleife, sichert täglich um $BACKUP_UHRZEIT (Standard 03:30)
#   backup.sh once     — genau einmal sichern (z. B. vor einem Update)
#
# Ziel ist /backup im Container; per NOTEN_BACKUP_DIR in .env auf einen Host-Pfad legen.
# Ältere Sicherungen werden nach $BACKUP_KEEP_DAYS Tagen gelöscht.
set -eu

ZIEL=/backup
QUELLE=/data
UHRZEIT="${BACKUP_UHRZEIT:-03:30}"
KEEP="${BACKUP_KEEP_DAYS:-14}"

log() { echo "[backup] $(date '+%Y-%m-%d %H:%M:%S') $*"; }

sichern() {
  stempel="$(date '+%Y%m%d-%H%M%S')"
  arbeit="$ZIEL/.unfertig-$stempel"
  mkdir -p "$arbeit"

  log "Datenbank sichern …"
  # --clean --if-exists: der Dump lässt sich in eine bestehende DB zurückspielen
  pg_dump --clean --if-exists --no-owner --no-privileges | gzip -9 > "$arbeit/db.sql.gz"

  log "Objektspeicher sichern …"
  # /data ist read-only eingebunden — hier wird nur gelesen
  tar -czf "$arbeit/data.tar.gz" -C "$QUELLE" .

  # Prüfsummen, damit sich eine Sicherung später verifizieren lässt
  (cd "$arbeit" && sha256sum db.sql.gz data.tar.gz > SHA256SUMS)

  # Erst nach vollständigem Schreiben umbenennen — halbe Sicherungen sind so erkennbar
  mv "$arbeit" "$ZIEL/$stempel"
  log "fertig: $ZIEL/$stempel ($(du -sh "$ZIEL/$stempel" | cut -f1))"

  log "alte Sicherungen (> $KEEP Tage) entfernen …"
  find "$ZIEL" -maxdepth 1 -type d -name '20*' -mtime "+$KEEP" -exec rm -rf {} + 2>/dev/null || true
  # liegengebliebene Abbrüche aufräumen
  find "$ZIEL" -maxdepth 1 -type d -name '.unfertig-*' -mtime +1 -exec rm -rf {} + 2>/dev/null || true
}

# führende Null entfernen — sonst liest die Shell "08"/"09" als ungültige Oktalzahl
ohne_null() { z="${1#0}"; echo "${z:-0}"; }

sekunden_bis() {
  # Sekunden bis zur nächsten Uhrzeit HH:MM (heute oder morgen) — ohne "date -d",
  # das es in BusyBox nicht in der GNU-Form gibt.
  jetzt=$(( $(ohne_null "$(date +%H)") * 3600 + $(ohne_null "$(date +%M)") * 60 + $(ohne_null "$(date +%S)") ))
  ziel=$(( $(ohne_null "${UHRZEIT%%:*}") * 3600 + $(ohne_null "${UHRZEIT##*:}") * 60 ))
  diff=$((ziel - jetzt))
  [ "$diff" -le 0 ] && diff=$((diff + 86400))
  echo "$diff"
}

case "${1:-daemon}" in
  once)
    sichern
    ;;
  daemon)
    log "Sicherung aktiv — täglich um $UHRZEIT, Aufbewahrung $KEEP Tage, Ziel $ZIEL"
    while true; do
      warte=$(sekunden_bis)
      log "nächste Sicherung in $((warte / 3600)) h $(((warte % 3600) / 60)) min"
      sleep "$warte"
      sichern || log "FEHLER bei der Sicherung — nächster Versuch morgen"
    done
    ;;
  *)
    echo "Aufruf: backup.sh [daemon|once]" >&2
    exit 2
    ;;
esac
