# Mitmachen

Danke fürs Interesse. Dieses Projekt entsteht für die tägliche Arbeit an einer
Kirchenmusikstelle — es soll dort gut sein und nicht überall ein bisschen.

## Fehler melden

Ein Issue mit: was du getan hast, was passiert ist, was du erwartet hast, Version bzw. Tag und
Art der Installation (Docker-Stack, eigenes Setup). Bei Anzeigeproblemen hilft ein Screenshot,
bei Server-Fehlern der Auszug aus `docker compose logs app`.

**Sicherheitslücken bitte nicht als Issue** — siehe [SECURITY.md](SECURITY.md).

## Änderungen vorschlagen

Bei allem, was mehr ist als ein Tippfehler: **erst ein Issue**, damit wir uns über die Richtung
einig sind, bevor du Zeit investierst. Danach:

```bash
uv sync
scripts/devdb.sh                # PostgreSQL für Entwicklung (macOS; sonst Docker, s. README)
uv run alembic upgrade head
uv run pytest -q                # muss grün sein
cd web && npm install && npm run build
```

Für den Pull Request:

- **Ein Thema pro PR.** Kleine, nachvollziehbare Änderungen werden schnell angesehen.
- **Tests** für neue Logik, besonders bei allem, was hochgeladene Dateien anfasst.
- **Migrationen** mit Alembic (`uv run alembic revision -m "…"`), niemals Schemaänderungen von Hand.
- Keine neuen Abhängigkeiten ohne guten Grund — jede vergrößert die Angriffsfläche. Wenn doch,
  bitte im Issue begründen und die Lizenz nennen (siehe [THIRD-PARTY.md](THIRD-PARTY.md)).

## Sprache und Stil

- **Projektsprache ist Deutsch**: Oberfläche, Kommentare, Commit-Nachrichten und Issues.
  Bezeichner im Code sind gemischt (Fachbegriffe deutsch: `werk`, `ausgabe`, `setliste`;
  Technisches englisch) — halte dich an das, was in der Datei schon steht.
- Python: Typannotationen, `from __future__ import annotations`, kurze Funktionen.
  Kommentare erklären das *Warum*, nicht das *Was*.
- Vue: Composition API mit `<script setup>`, Styles über die Tokens aus `brand/tokens.css` —
  keine fest eingetragenen Farben.

## Grundsätze, die nicht verhandelbar sind

1. **Hochgeladene Dateien sind feindlich.** Jede neue Verarbeitung von Fremddateien läuft über
   die vorhandene Validierung und im Sandbox-Subprozess.
2. **Keine Selbstregistrierung, keine Abschwächung der 2FA-Pflicht** als Standardeinstellung.
3. **Kein Nachhause-Telefonieren.** Die Anwendung baut keine Verbindungen zu Diensten Dritter
   auf, die der Betreiber nicht selbst angestoßen hat — auch keine Telemetrie, keine
   Web-Schriftarten, keine CDN-Skripte.
4. **Das Copyright-Gate bleibt.** Funktionen, die es umgehen, werden nicht aufgenommen.

## Lizenz

Mit deinem Beitrag stimmst du zu, dass er unter **AGPL-3.0-or-later** veröffentlicht wird.
