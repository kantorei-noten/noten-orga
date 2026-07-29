# Sicherheitslücken melden

Kantorei ist dafür gedacht, offen im Internet erreichbar zu sein. Hinweise auf Schwachstellen
sind darum ausdrücklich willkommen.

**Bitte kein öffentliches Issue anlegen.** Nutze stattdessen die private Meldung über GitHub:
*Security* → *Report a vulnerability* (GitHub Private Vulnerability Reporting). Nur der
Maintainer sieht die Meldung.

Hilfreich sind: betroffene Version oder Commit, Aufbau der Installation (Docker-Stack oder
eigenes Setup), Schritte zum Nachvollziehen und eine Einschätzung der Auswirkung.

**Antwortzeit:** Dies ist ein Feierabendprojekt einer einzelnen Person. Ich bestätige den
Eingang, so schnell ich kann — in der Regel innerhalb einer Woche. Bitte gib mir 90 Tage Zeit,
bevor du Details veröffentlichst; bei einer aktiv ausgenutzten Lücke sprechen wir uns kürzer ab.

## Unterstützte Versionen

Sicherheitskorrekturen erscheinen für den **jeweils neuesten Release-Tag**. Ältere Stände werden
nicht rückwirkend gepflegt — halte deine Installation aktuell (`docker compose pull && docker compose up -d`).

## Was bereits abgesichert ist

Damit Meldungen nicht doppelt kommen — folgende Maßnahmen sind vorhanden:

- **Anmeldung:** Argon2id-Hashes, TOTP-Zwei-Faktor als Pflicht, keine Selbstregistrierung,
  Rate-Limit und Kontosperre nach Fehlversuchen, gleichlautende Antwort bei falschem Namen und
  falschem Passwort (keine Konto-Enumeration), httpOnly/SameSite-Cookies mit `secure` im Betrieb
- **Hochgeladene Dateien** (die größte Angriffsfläche): Prüfung der Magic Bytes, harte Größen-
  und Seitenlimits, XML ausschließlich über `defusedxml` (kein XXE, keine Billion-Laughs),
  Entpacken von `.mxl` mit Grenzen für Anzahl, Gesamtgröße und Kompressionsverhältnis sowie
  Schutz gegen Zip-Slip, Pillow-Limit gegen Dekompressionsbomben. Das Parsen läuft in einem
  **eigenen Subprozess** mit RLIMIT für Speicher und CPU sowie Wall-Clock-Timeout; ein
  ClamAV-Anschluss ist vorbereitet (`NOTEN_CLAMAV_SOCKET`)
- **Ablage:** Uploads liegen außerhalb des Web-Roots und werden nie ausgeliefert, ohne dass die
  Anwendung sie kennt; Dateinamen aus Uploads werden nicht als Pfade übernommen
- **Betrieb:** nur Caddy veröffentlicht Ports, Container laufen als Nicht-Root, im Produktivmodus
  gibt es keine OpenAPI-Oberfläche, der Health-Endpunkt gibt keine Versions- oder Fehlerdetails
  preis, Caddy setzt CSP, HSTS, `X-Content-Type-Options` und `X-Frame-Options: DENY`

## Was ausdrücklich nicht abgedeckt ist

- Angriffe, die einen bereits kompromittierten Admin-Zugang voraussetzen
- Denial of Service durch schiere Last (setze davor einen Reverse-Proxy mit Rate-Limit)
- Schwachstellen in Docker, dem Betriebssystem oder dem Reverse-Proxy des Betreibers
- Fragen zum Urheberrecht eingestellter Noten — dazu siehe [RECHTLICHES.md](RECHTLICHES.md)
