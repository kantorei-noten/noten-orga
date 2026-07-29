# Der Docker-Stack im Detail

Der Schnellstart steht im [Haupt-README](../README.md). Hier stehen Aufbau, Schalter und
Fehlersuche.

## Aufbau

| Service | Image | Rolle | Von außen erreichbar |
|---|---|---|---|
| **caddy** | `…/web` | PWA ausliefern, Reverse-Proxy, TLS, Sicherheits-Header | **ja — nur dieser** (80/443) |
| **app** | `…/app` | FastAPI, Datei-Prüfung und -Parsen im Sandbox-Subprozess | nein |
| **worker** | `…/worker` | schwere Jobs: Harmonieanalyse (music21), Importe | nein |
| **db** | `postgres:17-alpine` | Daten | nein |
| **backup** | `…/backup` | nächtliche Sicherung von DB und Objektspeicher | nein |

App und Worker teilen sich das `data`-Volume (Objektspeicher) und die Datenbank. Migrationen
laufen automatisch beim Start der App (`alembic upgrade head`).

Die Images kommen von `ghcr.io/kantorei-noten/noten-orga/{app,worker,web,backup}` und gibt es
für amd64 und arm64. Selbst bauen:

```bash
docker compose -f compose.yaml -f compose.build.yaml up -d --build
```

## Schalter in der `.env`

`./setup.sh` legt die Datei mit zufälligen Geheimnissen an; alle Möglichkeiten stehen in
[`.env.example`](.env.example). Die wichtigsten:

| Variable | Standard | Bedeutung |
|---|---|---|
| `NOTEN_DOMAIN` | *(leer)* | Domain → automatisches Let's-Encrypt-Zertifikat. Leer = `:80` ohne TLS |
| `NOTEN_SECURE_COOKIES` | `true` | Muss auf `false`, wenn ohne HTTPS betrieben — sonst schlägt der Login fehl |
| `NOTEN_VERSION` | `latest` | Fester Release-Tag (`v0.1.0`) ist im Produktivbetrieb die bessere Wahl |
| `NOTEN_HTTP_PORT` / `NOTEN_HTTPS_PORT` | `80` / `443` | Für NAS oder Server, auf denen die Ports belegt sind |
| `NOTEN_BACKUP_DIR` | `backups` | Host-Pfad (empfohlen) oder das gleichnamige Docker-Volume |
| `TZ` | `Europe/Berlin` | Zeitzone für die Sicherungs-Uhrzeit — ohne sie liefe sie nach UTC |
| `NOTEN_TOTP_PFLICHT` | `true` | Zwei-Faktor für alle Konten. Nur zum Ausprobieren abschalten |

## Sicherung

Der `backup`-Container schläft bis `NOTEN_BACKUP_UHRZEIT` und legt dann unter
`NOTEN_BACKUP_DIR/<Zeitstempel>/` ab:

- `db.sql.gz` — `pg_dump --clean --if-exists`, direkt zurückspielbar
- `data.tar.gz` — der komplette Objektspeicher (Scans, MusicXML, Vorschaubilder)
- `SHA256SUMS` — zum späteren Prüfen

Ein Verzeichnis entsteht erst, wenn beides vollständig geschrieben ist (vorher heißt es
`.unfertig-…`) — ein abgebrochener Lauf ist also erkennbar. Sicherungen älter als
`NOTEN_BACKUP_KEEP_DAYS` werden entfernt.

Sofort sichern (etwa vor einem Update): `docker compose run --rm backup once`.
Zurückspielen: siehe [Haupt-README](../README.md#betrieb).

Die Sicherung liegt standardmäßig auf demselben Rechner. Für den Ernstfall (Diebstahl, Brand,
Verschlüsselungstrojaner) gehört eine Kopie **außer Haus** — etwa per `restic`/`rclone` vom
Host aus auf ein Cloud-Ziel.

Die Backup-Seite in der Anwendung selbst steuert den systemd-Timer einer klassischen
Server-Installation; im Docker-Betrieb ist stattdessen dieser Container zuständig.

## Fehlersuche

```bash
docker compose ps                 # Zustand aller Container (app hat einen Healthcheck)
docker compose logs -f app        # API-Log inkl. Migrationen beim Start
docker compose logs caddy         # TLS- und Proxy-Probleme
docker compose logs backup        # wann die nächste Sicherung läuft
```

**Kein Zertifikat / Caddy meldet Fehler:** Der A-Record von `NOTEN_DOMAIN` muss auf diesen
Server zeigen und die Ports 80 und 443 müssen von außen erreichbar sein. Let's Encrypt hat
Ratenbegrenzungen — bei wiederholten Versuchen kurz warten.

**Login funktioniert nicht ohne HTTPS:** `NOTEN_SECURE_COOKIES=false` setzen, sonst sendet der
Browser das Sitzungs-Cookie über `http` nicht.

**„Port already in use" auf dem NAS:** `NOTEN_HTTP_PORT`/`NOTEN_HTTPS_PORT` in der `.env`
umstellen und den vorhandenen Reverse-Proxy auf diese Ports zeigen lassen.

**App startet nicht, DB-Fehler im Log:** Die DB braucht beim ersten Start ein paar Sekunden;
`depends_on` wartet auf den Healthcheck. Bleibt es dabei, prüfen, ob `NOTEN_DB_PASSWORD`
nachträglich geändert wurde — das Passwort im Volume der Datenbank bleibt das alte.

**music21-Jobs bleiben liegen:** `docker compose logs worker`. Der Worker holt Aufträge aus der
Tabelle `job`; ohne laufenden Worker bleiben sie auf `offen` stehen.

## Warum music21 nur im Worker läuft

`music21` ist schwergewichtig (numpy und mehr) und verarbeitet nicht vertrauenswürdiges
MusicXML. Deshalb steckt es **nicht** im schlanken, von außen erreichbaren App-Image, sondern im
separaten Worker (Abhängigkeitsgruppe `worker` in `pyproject.toml`). Die App legt nur einen
Auftrag in der Tabelle `job` an; der Worker arbeitet ihn ab und meldet den Fortschritt zurück,
den die Oberfläche über `GET /api/jobs/{id}` abfragt.

## Noch offen

- Import mit Fortschrittsanzeige in den Einstellungen (die Job-Infrastruktur steht bereits)
- Vollständig isolierter Parser-Container (`network_mode: none`, `cap_drop: ALL`, read-only)
- Offsite-Sicherung als eigener Container
