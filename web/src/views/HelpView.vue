<script setup>
const abschnitte = [
  ['anmelden', 'Anmelden'],
  ['finden', 'Finden: Katalog & Suche'],
  ['werk', 'Ein Werk öffnen'],
  ['spielen', 'Ansehen, Spielmodus & Notizen'],
  ['setlisten', 'Setlisten (Gottesdienst-Ablauf)'],
  ['projektion', 'Projektion & Drucken'],
  ['sammlungen', 'Sammlungen'],
  ['dienste', 'Dienste (Chor · Termine · Zusagen)'],
  ['chordpro', 'ChordPro (Text & Akkorde)'],
  ['metronom', 'Metronom'],
  ['einstellungen', 'Einstellungen'],
  ['benutzer', 'Benutzer (nur Admin)']
]
</script>

<template>
  <div class="hilfe">
    <h1>Hilfe &amp; Anleitung</h1>
    <p class="lead">
      Willkommen im <b>Kantorei-Notenarchiv</b>. Diese Seite zeigt Schritt für Schritt, wie alles funktioniert —
      mit Bildern aus der laufenden App. Klick oben in der Leiste auf einen Bereich oder springe hier direkt hin:
    </p>
    <ul class="toc">
      <li v-for="a in abschnitte" :key="a[0]"><a :href="'#' + a[0]">{{ a[1] }}</a></li>
    </ul>

    <section id="anmelden">
      <h2>Anmelden</h2>
      <p>Melde dich mit <b>Benutzername</b> und <b>Passwort</b> an. Ist die Zwei-Faktor-Anmeldung (2FA) aktiv,
        kommt zusätzlich ein 6-stelliger Code aus deiner Authenticator-App dazu. Konten legt der <b>Admin</b> an —
        eine Selbstregistrierung gibt es bewusst nicht.</p>
      <figure><img src="/hilfe/01-login.png" alt="Anmeldung" /></figure>
    </section>

    <section id="finden">
      <h2>Finden: Katalog &amp; Suche</h2>
      <p>Der <b>Katalog</b> listet alle Werke. Oben rechts schaltest du zwischen <b>Liste</b> und <b>Baum</b> um.</p>
      <figure><img src="/hilfe/02-katalog.png" alt="Katalog" /></figure>
      <p>Im <b>Baum</b> gruppierst du nach <b>Komponist</b>, <b>Gattung</b> oder <b>Anlass</b> und klappst die Gruppen auf —
        ideal bei tausenden Stücken.</p>
      <figure><img src="/hilfe/03-katalog-baum.png" alt="Katalog als Baum" /></figure>
      <p>Über <b>Suche</b> findest du nach Titel, Komponist oder GL/EG-Nummer — mit Filtern (Gattung, Besetzung, Rechte)
        und unscharfer Treffersuche.</p>
      <figure><img src="/hilfe/04-suche.png" alt="Suche" /></figure>
    </section>

    <section id="werk">
      <h2>Ein Werk öffnen</h2>
      <p>Ein Klick auf ein Werk öffnet die Detailseite mit allen <b>Ausgaben &amp; Dateien</b>. Hier findest du je Blatt
        die Aktionen <b>Ansehen</b>, <b>Spielen</b> (Spielmodus), <b>Notizen</b> und <b>Löschen</b>, kannst per
        <b>„Zu Setliste"</b> das Stück in einen Ablauf legen und den <b>Rechtestatus</b> setzen (nur „gemeinfrei"
        oder „lizenziert" darf gedruckt/gebündelt werden).</p>
      <figure><img src="/hilfe/05-werk.png" alt="Werk-Ansicht" /></figure>
      <ul>
        <li><b>Bearbeiten ✎</b> / <b>Löschen</b> (oben rechts): Titel, Komponist, Gattung … ändern oder das Werk entfernen.</li>
        <li><b>Dateien hinzufügen</b>: PDF oder MusicXML per Klick oder Drag &amp; Drop anhängen.</li>
        <li><b>Text &amp; Akkorde (ChordPro)</b> und <b>Projektionstext</b> lassen sich weiter unten pflegen bzw.
          <b>aus den Noten erzeugen</b>.</li>
      </ul>
    </section>

    <section id="spielen">
      <h2>Ansehen, Spielmodus &amp; Notizen</h2>
      <ul>
        <li><b>Ansehen</b> öffnet das Notenblatt als PDF — schnell zum Durchblättern.</li>
        <li><b>Spielmodus ▸</b> ist die Vollbild-Ansicht fürs Instrument/iPad: Tap-Zonen links/rechts zum Blättern,
          Zwei-Seiten, Auto-Scroll, Dunkel/Rotlicht, „An Fenster anpassen" und Bluetooth-Fußpedal.</li>
        <li><b>Notizen ✎</b>: direkt auf dem Blatt zeichnen oder Text setzen (verschiebbar, Schriftgröße) — die
          Noten liegen als Hintergrund darunter. Notizblätter lassen sich ansehen, spielen, drucken und versenden.</li>
      </ul>
    </section>

    <section id="setlisten">
      <h2>Setlisten (Gottesdienst-Ablauf)</h2>
      <p>Eine <b>Setliste</b> ist die Reihenfolge für einen Gottesdienst oder ein Konzert.</p>
      <figure><img src="/hilfe/06-setlisten.png" alt="Setlisten" /></figure>
      <p>In der Setliste fügst du Werke hinzu (mit Wahl von <b>Blatt</b> und <b>Seitenbereich</b>) und
        <b>Zwischenüberschriften</b> zum Gliedern. Einträge lassen sich per ✎ nachträglich ändern, per ↑ ↓ umsortieren
        und per Klick direkt öffnen.</p>
      <figure><img src="/hilfe/07-setliste.png" alt="Setliste bearbeiten" /></figure>
    </section>

    <section id="projektion">
      <h2>Projektion &amp; Drucken</h2>
      <ul>
        <li><b>Spielen</b>: die ganze Setliste am Stück im Spielmodus.</li>
        <li><b>Projektion</b> (für den Beamer): umschaltbar <b>Titel</b> · <b>Liedtext</b> · <b>Noten</b> · <b>Beides</b>.
          Weiter mit Pfeiltasten oder Tippen links/rechts.</li>
        <li><b>Drucken (PDF)</b>: erzeugt ein Sammel-PDF der Setliste mit <b>A4</b>-Normalisierung und <b>Bundsteg</b>
          fürs Binden. Gesperrte Rechtestatus-Stücke bleiben außen vor.</li>
      </ul>
    </section>

    <section id="sammlungen">
      <h2>Sammlungen</h2>
      <p><b>Sammlungen</b> sind thematische Unter-Bibliotheken (z. B. „Orgel-Repertoire", „Chor"). Lege eine an,
        füge Werke aus dem Katalog hinzu, benenne sie um oder lösche sie in der Detailansicht.</p>
      <figure><img src="/hilfe/08-sammlungen.png" alt="Sammlungen" /></figure>
    </section>

    <section id="dienste">
      <h2>Dienste (Chor · Termine · Zusagen)</h2>
      <p>Unter <b>Dienste</b> verwaltest du <b>Gruppen</b> (Chor/Bläser/Band), ihre <b>Mitglieder</b> und die
        <b>Termine</b>. Termine gibt's als Liste oder <b>Kalender</b>.</p>
      <figure><img src="/hilfe/09-dienste.png" alt="Dienste" /></figure>
      <ul>
        <li><b>Meine Dienste</b> (ganz oben): jede/r sieht die eigenen Termine und sagt zu (<b>„Ich kann ✓"</b>) oder
          ab, mit optionaler Notiz.</li>
        <li>Der/die Verantwortliche sieht je Termin <b>alle Zusagen/Absagen</b> und kann Datum/Setliste/Notiz ändern.</li>
        <li><b>Drucken</b>: der ganze Dienstplan als Liste mit Gruppen, Mitgliedern und Status.</li>
      </ul>
    </section>

    <section id="chordpro">
      <h2>ChordPro (Text &amp; Akkorde)</h2>
      <p><b>ChordPro</b> zeigt Akkorde direkt <b>über den Silben</b>. Beim Bearbeiten musst du keine Syntax tippen —
        nutze die <b>Token</b> (anklicken/ziehen). Mit <b>Halbtöne −/+</b> transponierst du alles auf einmal; das
        Ergebnis lässt sich mit <b>Griffbildern</b> drucken, speichern und versenden. Zu jedem Werk lässt sich
        ChordPro <b>aus den Noten erzeugen</b>.</p>
      <figure><img src="/hilfe/10-chordpro.png" alt="ChordPro" /></figure>
    </section>

    <section id="metronom">
      <h2>Metronom</h2>
      <p>Ein einfaches <b>Metronom</b> mit Tempo, Taktart und Tap-Tempo.</p>
      <figure><img src="/hilfe/11-metronom.png" alt="Metronom" /></figure>
    </section>

    <section id="einstellungen">
      <h2>Einstellungen</h2>
      <p>Hier änderst du dein <b>Passwort</b>. Als <b>Admin</b> pflegst du zusätzlich:</p>
      <figure><img src="/hilfe/12-einstellungen.png" alt="Einstellungen" /></figure>
      <ul>
        <li><b>Auswahllisten</b>: Besetzungen, Sammlungs-Arten und Anlässe (die Aufklapp-Listen beim Erfassen).</li>
        <li><b>Rechtestatus (Massen-Aktion)</b>: vielen Ausgaben auf einmal einen Status geben — z. B. den
          gemeinfreien Bestand fürs Drucken freigeben.</li>
        <li><b>Backup</b>: Ziel, Aufbewahrung und Uhrzeit des nächtlichen Backups.</li>
        <li><b>Aufgaben &amp; Import</b>: längere Aufgaben (Noten-Import, Analyse) anstoßen und den <b>Fortschritt</b>
          live verfolgen.</li>
      </ul>
    </section>

    <section id="benutzer">
      <h2>Benutzer (nur Admin)</h2>
      <p>Der Admin legt <b>Konten</b> an (kein Self-Signup), vergibt Rollen (Admin/Musiker/Chor/Gast), setzt bei
        Bedarf ein neues Passwort, schaltet <b>2FA</b> pro Person ein/aus und löscht Konten. Der letzte aktive
        Admin ist gegen Löschen geschützt.</p>
      <figure><img src="/hilfe/13-benutzer.png" alt="Benutzerverwaltung" /></figure>
    </section>

    <p class="ende muted">Fehlt etwas oder klemmt etwas? Frag deinen Admin — oder schau, ob eine neue Version bereitsteht (Seite einmal hart neu laden).</p>
  </div>
</template>

<style scoped>
.hilfe { max-width: 900px; }
.lead { color: var(--ink-2); max-width: 70ch; }
.toc { columns: 2; gap: 24px; list-style: none; padding: 12px 16px; margin: 14px 0 26px; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--surface); }
.toc li { margin: 4px 0; break-inside: avoid; }
.toc a { color: var(--accent-strong, var(--accent)); text-decoration: none; }
.toc a:hover { text-decoration: underline; }
section { margin: 0 0 34px; scroll-margin-top: 76px; }
section h2 { font-size: var(--text-xl, 1.35rem); margin: 0 0 8px; padding-top: 6px; border-top: 1px solid var(--border); }
section p, section ul { max-width: 74ch; }
section ul { padding-left: 20px; }
section li { margin: 5px 0; }
figure { margin: 14px 0; }
figure img { display: block; width: 100%; height: auto; border: 1px solid var(--border); border-radius: var(--radius-md); box-shadow: var(--shadow-1, 0 1px 4px rgba(0,0,0,0.08)); }
.ende { margin-top: 30px; }
@media (max-width: 640px) { .toc { columns: 1; } }
</style>
