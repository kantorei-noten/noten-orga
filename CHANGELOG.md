# Änderungen

Alle nennenswerten Änderungen dieses Projekts. Versionierung nach
[SemVer](https://semver.org/lang/de/); solange die Hauptversion 0 ist, können sich Schnittstellen
zwischen Nebenversionen ändern.

## v0.1.0 — 2026-07-29

Erste öffentliche Fassung.

**Archiv**
- Werke, Ausgaben, Dateien und Stimmen mit Metadaten (Komponist, Gattung, Besetzung, Tonart,
  Anlass, Gotteslob-/EG-Nummer, Rechtestatus)
- Katalog als Liste oder Baum, gruppiert nach Komponist, Gattung oder Anlass
- Volltextsuche (deutsch) mit unscharfer Treffersuche und Filtern
- Upload von PDF und MusicXML/.mxl mit Vorschaubildern und Dedup über Hash
- Sammlungen als thematische Unter-Bibliotheken

**Anzeige und Spiel**
- Spielmodus in Vollbild: Tap-Zonen, Zwei-Seiten-Ansicht, Auto-Scroll, Dunkel- und
  Rotlicht-Modus, Bluetooth-Fußpedal
- Notizen (Zeichnen und Text) auf einer eigenen Ebene über dem Notenblatt
- MusicXML-Wiedergabe mit Verovio, transponierbar
- PWA mit Offline-Fähigkeit für bereits geöffnete Inhalte

**Gottesdienst und Probe**
- Setlisten mit Seitenbereichen und Zwischenüberschriften
- Projektion für den Beamer (Titel, Liedtext, Noten, beides)
- Sammeldruck als A4-normalisiertes PDF mit Bundsteg, abgesichert durch das Copyright-Gate
- Dienste: Gruppen, Termine, Zu- und Absagen, Kalender, Dienstplan zum Drucken
- ChordPro mit Transposition und Griffbildern, auf Wunsch automatisch aus den Noten erzeugt
  (Harmonieanalyse mit music21 im Worker)
- Metronom

**Betrieb und Sicherheit**
- Docker-Stack aus Caddy, FastAPI, Worker, PostgreSQL 17 und Sicherungs-Container
- Fertige Images für amd64 und arm64 auf der GitHub Container Registry
- `setup.sh` erzeugt die `.env` mit zufälligen Geheimnissen
- Nächtliche Sicherung von Datenbank und Objektspeicher mit Aufbewahrungsgrenze und Prüfsummen
- Argon2id, Pflicht-TOTP, keine Selbstregistrierung, Rate-Limit und Kontosperre
- Gehärtete Verarbeitung hochgeladener Dateien: Magic-Byte-Prüfung, Größenlimits, `defusedxml`,
  Schutz gegen Zip-Bomben und Zip-Slip, Parsen im Subprozess mit Speicher-, CPU- und Zeitlimit
- Datenbankmigrationen laufen beim Start automatisch
