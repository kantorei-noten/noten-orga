# Noten, Urheberrecht und Import-Quellen

Kantorei ist ein **leeres Archiv**. Es werden **keine Noten mitgeliefert** — weder im Repository
noch in den Docker-Images. Was in deiner Installation landet, bringst du selbst hinein: durch
eigene Scans, eigene Dateien oder über die Import-Skripte.

## Verantwortung liegt beim Betreiber

Musiknoten sind urheberrechtlich geschützt, und zwar in zwei Schichten:

1. **Das Werk** (Komposition, Text) — Schutz endet in Deutschland 70 Jahre nach dem Tod des
   letzten Urhebers.
2. **Die Ausgabe** (Notensatz, Edition, Bearbeitung, Einrichtung) — kann eigenständig geschützt
   sein, selbst wenn das Werk gemeinfrei ist. Ein moderner Urtext-Nachdruck einer Bach-Kantate
   ist nicht automatisch frei.

Dazu kommen je nach Nutzung **Aufführungs- und Vervielfältigungsrechte** (in Deutschland
GEMA/VG Musikedition; für Kirchengemeinden gelten teils pauschale Verträge, etwa für das
Kopieren von Liedern im Gottesdienst). Diese Software prüft davon **nichts** automatisch und
kann es nicht — sie kennt nur, was du ihr an Metadaten gibst.

**Wer Kantorei betreibt, ist selbst dafür verantwortlich, nur Material einzustellen, zu
vervielfältigen und zugänglich zu machen, wozu er berechtigt ist.**

## Eingebautes Copyright-Gate

Jede Ausgabe (Edition) trägt einen Rechtestatus. Neue Ausgaben starten auf `unbekannt`:

| Status | Bedeutung | Drucken / Bündeln |
|---|---|---|
| `public_domain` | gemeinfrei — Werk **und** Ausgabe | erlaubt |
| `lizenziert` | Lizenz oder Erlaubnis liegt vor | erlaubt |
| `unbekannt` | ungeprüft (Standard bei jedem Upload) | **gesperrt** |
| `gesperrt` | ausdrücklich nicht verwendbar | **gesperrt** |

Der Sammeldruck (`app/print/service.py`) verweigert jede Ausgabe, die nicht `public_domain`
oder `lizenziert` ist. Die Ansicht am Bildschirm bleibt möglich — die Bewertung, ob das
zulässig ist, bleibt bei dir. Den Status setzt du pro Ausgabe in der Werkansicht oder als
Massen-Aktion unter *Einstellungen*.

Das Gate ist eine **Hilfe gegen Versehen, keine Rechtsprüfung**.

## Import-Skripte

Unter `scripts/` liegen Importer für offene Notenquellen. Sie laufen **nur, wenn du sie
ausführst**, und ziehen die Daten direkt von der jeweiligen Quelle — nichts davon ist Teil
dieses Repositorys.

| Skript | Quelle |
|---|---|
| `import_cpdl.py` | CPDL / ChoralWiki — <https://www.cpdl.org> |
| `import_mutopia.py` | Mutopia Project — <https://www.mutopiaproject.org> |
| `import_jrp.py` | Josquin Research Project — <https://josquin.stanford.edu> |
| `import_music21.py` | music21-Corpus (u. a. Bach-Choräle) — <https://www.music21.org> |

Jede dieser Quellen hat **eigene Nutzungsbedingungen**, die sich je nach einzelnem Stück
unterscheiden können (gemeinfrei, CC-Lizenzen mit Namensnennung, teils Einschränkungen für
kommerzielle Nutzung). Die Skripte übernehmen die Metadaten so, wie die Quelle sie liefert;
sie treffen **keine** Aussage darüber, ob deine geplante Nutzung zulässig ist. Prüfe die
Lizenzangaben der jeweiligen Quelle, bevor du importiertes Material verteilst, druckst oder
aufführst — und pflege den Rechtestatus in Kantorei entsprechend.

Bitte importiere freundlich: die Skripte drosseln ihre Anfragen und senden eine Kennung im
User-Agent. Trage über `NOTEN_IMPORT_KONTAKT` deine eigene Kontaktadresse ein, wenn du größere
Mengen holst.

## Marke und Gestaltung

Der Name **„Kantorei"**, das Logo und die Gestaltungsvorlagen unter `brand/` gehören zum
Projekt und stehen unter derselben Lizenz wie der Code. Wenn du einen Fork betreibst, benenne
ihn bitte erkennbar um — schon damit Nutzer eine geänderte Fassung von dieser unterscheiden
können.
