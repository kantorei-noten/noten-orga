<script setup>
import { onMounted, onUnmounted, ref } from 'vue'

import { api } from '@/api'
import RefListe from '@/components/RefListe.vue'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const alt = ref('')
const neu = ref('')
const neu2 = ref('')
const msg = ref('')
const fehler = ref('')
const busy = ref(false)

async function speichern() {
  fehler.value = ''
  msg.value = ''
  if (neu.value.length < 8) {
    fehler.value = 'Neues Passwort muss mindestens 8 Zeichen haben.'
    return
  }
  if (neu.value !== neu2.value) {
    fehler.value = 'Die neuen Passwörter stimmen nicht überein.'
    return
  }
  busy.value = true
  try {
    await api.post('/auth/passwort', { altes_passwort: alt.value, neues_passwort: neu.value })
    msg.value = 'Passwort geändert.'
    alt.value = neu.value = neu2.value = ''
  } catch (e) {
    fehler.value = e.status === 400 ? 'Aktuelles Passwort ist falsch.' : 'Fehler: ' + e.message
  } finally {
    busy.value = false
  }
}

// Rechtestatus in Masse setzen (Admin) — z. B. importierten gemeinfreien Bestand freigeben
const RECHTE = [
  ['public_domain', 'gemeinfrei'],
  ['lizenziert', 'lizenziert'],
  ['unbekannt', 'unbekannt'],
  ['gesperrt', 'gesperrt']
]
const rmVon = ref('unbekannt')
const rmAuf = ref('public_domain')
const rmMsg = ref('')
async function rechteMasse() {
  if (!confirm(`Wirklich ALLE Ausgaben mit Status „${rmVon.value}" auf „${rmAuf.value}" setzen?`)) return
  rmMsg.value = 'Setze …'
  try {
    const r = await api.post('/ausgaben/rechtestatus-masse', { von: rmVon.value, auf: rmAuf.value })
    rmMsg.value = `${r.geaendert} Ausgaben geändert.`
  } catch (e) {
    rmMsg.value = 'Fehler: ' + e.message
  }
}

// Backup: Ziel / Aufbewahrung / Uhrzeit (Admin)
const bkCfg = ref(null)
const bkMsg = ref('')
async function ladeBackup() {
  try {
    bkCfg.value = await api.get('/backup/config')
  } catch {
    bkCfg.value = null
  }
}
async function speichereBackup() {
  bkMsg.value = 'Speichern …'
  try {
    const r = await api.put('/backup/config', {
      ziel: (bkCfg.value.ziel || '').trim(),
      keep_daily: Number(bkCfg.value.keep_daily),
      keep_weekly: Number(bkCfg.value.keep_weekly),
      keep_monthly: Number(bkCfg.value.keep_monthly),
      uhrzeit: bkCfg.value.uhrzeit
    })
    bkMsg.value = r.hinweis || 'Gespeichert.'
  } catch (e) {
    bkMsg.value = e.status === 400 ? e.message : 'Fehler: ' + e.message
  }
}

// Aufgaben & Import (Jobs; abgearbeitet vom Worker-Container)
const JOBNAMEN = {
  chordpro_music21: 'ChordPro aus Noten (music21)',
  import_bach: 'Bach-Choräle importieren (music21)',
  import_mutopia: 'Mutopia-Noten importieren',
  import_cpdl: 'CPDL/ChoralWiki importieren'
}
const cpdlKat = ref('Masses')
const jobs = ref([])
let jobTimer = null
function jobName(t) {
  return JOBNAMEN[t] || t
}
function pct(j) {
  return j.gesamt > 0 ? Math.round((100 * j.fortschritt) / j.gesamt) : j.status === 'fertig' ? 100 : 0
}
async function ladeJobs() {
  try {
    jobs.value = await api.get('/jobs')
  } catch {
    jobs.value = []
  }
}
function pollen() {
  clearTimeout(jobTimer)
  if (jobs.value.some((j) => j.status === 'offen' || j.status === 'laeuft')) {
    jobTimer = setTimeout(async () => {
      await ladeJobs()
      pollen()
    }, 2500)
  }
}
async function jobStart(typ, params = {}) {
  try {
    await api.post('/jobs', { typ, params })
    await ladeJobs()
    pollen()
  } catch (e) {
    alert(e.status === 409 ? 'Diese Aufgabe läuft bereits.' : 'Fehler: ' + e.message)
  }
}
async function jobAbbrechen(j) {
  await api.post(`/jobs/${j.id}/abbrechen`)
  await ladeJobs()
}

onMounted(() => {
  if (auth.istAdmin) {
    ladeBackup()
    ladeJobs().then(pollen)
  }
})
onUnmounted(() => clearTimeout(jobTimer))
</script>

<template>
  <h1>Einstellungen</h1>
  <p class="muted">Angemeldet als <b>{{ auth.user?.benutzername }}</b> ({{ auth.rolle }})</p>
  <div class="card" style="max-width: 420px; margin-top: 12px">
    <b>Passwort ändern</b>
    <label class="field" style="margin-top: 10px"><span>Aktuelles Passwort</span>
      <input class="input" type="password" v-model="alt" autocomplete="current-password" />
    </label>
    <label class="field"><span>Neues Passwort (min. 8 Zeichen)</span>
      <input class="input" type="password" v-model="neu" autocomplete="new-password" />
    </label>
    <label class="field"><span>Neues Passwort wiederholen</span>
      <input class="input" type="password" v-model="neu2" autocomplete="new-password" />
    </label>
    <p v-if="fehler" class="error">{{ fehler }}</p>
    <p v-if="msg" class="muted" style="color: var(--success)">{{ msg }}</p>
    <button class="btn primary" :disabled="busy" @click="speichern">Speichern</button>
  </div>

  <template v-if="auth.darfSchreiben">
    <h2 style="margin-top: 26px">Auswahllisten</h2>
    <p class="muted">Diese Begriffe erscheinen in den Aufklapp-Listen (Werk erfassen, Sammlungen). Bearbeiten, hinzufügen, sortieren.</p>
    <div style="max-width: 640px; margin-top: 12px">
      <RefListe
        titel="Besetzungen"
        endpoint="/besetzungen"
        :hat-kuerzel="true"
        hinweis="Das Kürzel (z. B. SATB) wird an den Werken gespeichert und lässt sich nicht mehr ändern; verwendete Besetzungen können nicht gelöscht werden."
      />
      <RefListe
        titel="Sammlungs-Arten"
        endpoint="/sammlung-arten"
        :hat-kuerzel="true"
        hinweis="Arten für Sammlungen (orgel, chor …). In Verwendung befindliche Arten können nicht gelöscht werden."
      />
      <RefListe
        titel="Anlässe / Kirchenjahr"
        endpoint="/anlaesse"
        :hat-kuerzel="false"
        hinweis="Löschen entfernt auch die Zuordnung an betroffenen Werken."
      />
    </div>
  </template>

  <template v-if="auth.istAdmin">
    <h2 style="margin-top: 26px">Rechtestatus (Massen-Aktion)</h2>
    <div class="card" style="max-width: 640px; margin-top: 12px">
      <p class="muted">
        Nur <b>gemeinfreie</b> oder <b>lizenzierte</b> Ausgaben dürfen gebündelt/gedruckt/weitergegeben werden.
        Importierter Bestand steht auf <b>unbekannt</b> und ist dadurch gesperrt. Hier lässt sich der Status vieler
        Ausgaben auf einmal setzen — z. B. den gemeinfreien Bestand freigeben.
      </p>
      <p class="muted" style="font-size: 12px; margin: 6px 0 0">
        Achtung: Das ist eine rechtliche Zusicherung. Nur anwenden, wenn die Quellen wirklich gemeinfrei/lizenziert sind.
      </p>
      <div class="toolbar" style="margin: 10px 0 0; flex-wrap: wrap; gap: 10px; align-items: flex-end">
        <label class="field" style="max-width: 170px"><span>von Status</span>
          <select class="input" v-model="rmVon"><option v-for="r in RECHTE" :key="r[0]" :value="r[0]">{{ r[1] }}</option></select>
        </label>
        <label class="field" style="max-width: 170px"><span>auf Status</span>
          <select class="input" v-model="rmAuf"><option v-for="r in RECHTE" :key="r[0]" :value="r[0]">{{ r[1] }}</option></select>
        </label>
        <button class="btn secondary" @click="rechteMasse">Setzen</button>
        <span class="muted">{{ rmMsg }}</span>
      </div>
    </div>

    <h2 style="margin-top: 26px">Backup</h2>
    <div v-if="bkCfg" class="card" style="max-width: 640px; margin-top: 12px">
      <p class="muted">Wohin, wie viele und wann das nächtliche Backup geschrieben wird.</p>
      <div class="bgrid" style="margin-top: 10px">
        <label class="field wide"><span>Ziel (Repository-Pfad)</span>
          <input class="input" v-model="bkCfg.ziel" placeholder="/var/backups/noten/repo" />
        </label>
        <label class="field"><span>Uhrzeit (täglich)</span><input class="input" type="time" v-model="bkCfg.uhrzeit" /></label>
        <label class="field"><span>Aufbewahrung: täglich</span><input class="input" type="number" min="0" v-model="bkCfg.keep_daily" /></label>
        <label class="field"><span>… wöchentlich</span><input class="input" type="number" min="0" v-model="bkCfg.keep_weekly" /></label>
        <label class="field"><span>… monatlich</span><input class="input" type="number" min="0" v-model="bkCfg.keep_monthly" /></label>
      </div>
      <div class="toolbar" style="margin-top: 10px">
        <button class="btn primary" @click="speichereBackup">Speichern</button>
        <span class="muted">{{ bkMsg }}</span>
      </div>
      <p class="muted" style="font-size: 12px; margin: 6px 0 0">
        Ein Offsite-Ziel (Backblaze B2 / S3, für echtes 3-2-1) hat Vorrang und wird separat verschlüsselt in
        <code>/opt/noten/secrets/restic.env</code> hinterlegt.
      </p>
    </div>

    <h2 style="margin-top: 26px">Aufgaben &amp; Import</h2>
    <div class="card" style="max-width: 640px; margin-top: 12px">
      <p class="muted">Längere Aufgaben (Import, music21-Analyse) laufen im Hintergrund. Fortschritt live.</p>
      <div class="toolbar" style="margin: 10px 0 0; flex-wrap: wrap">
        <button class="btn secondary" @click="jobStart('import_bach')">Bach-Choräle importieren</button>
        <button class="btn secondary" @click="jobStart('import_mutopia')">Mutopia importieren</button>
        <button class="btn secondary" @click="jobStart('chordpro_music21')">ChordPro aus Noten erzeugen</button>
      </div>
      <div class="toolbar" style="margin: 8px 0 0; flex-wrap: wrap; align-items: flex-end; gap: 8px">
        <label class="field" style="max-width: 180px"><span>CPDL-Kategorie</span>
          <input class="input" v-model="cpdlKat" placeholder="Masses, Motets, Anthems …" />
        </label>
        <button class="btn secondary" @click="jobStart('import_cpdl', { category: cpdlKat.trim(), only_sacred: true })">CPDL importieren</button>
      </div>

      <div v-if="jobs.length" class="stack" style="margin-top: 12px">
        <div v-for="j in jobs" :key="j.id" class="jrow">
          <div class="jhead">
            <b>{{ jobName(j.typ) }}</b>
            <span class="tag jstat" :class="j.status">{{ j.status }}</span>
            <button v-if="j.status === 'offen' || j.status === 'laeuft'" class="btn sm ghost" @click="jobAbbrechen(j)">Abbrechen</button>
          </div>
          <div class="pbar"><div class="pfill" :style="{ width: pct(j) + '%' }" /></div>
          <div class="sub">
            {{ pct(j) }}%<template v-if="j.gesamt"> · {{ j.fortschritt }}/{{ j.gesamt }}</template><template v-if="j.aktuell"> · {{ j.aktuell }}</template>
          </div>
          <details v-if="j.log"><summary class="muted" style="font-size: 12px; cursor: pointer">Log</summary><pre class="jlog">{{ j.log }}</pre></details>
        </div>
      </div>
      <p class="muted" style="font-size: 12px; margin: 8px 0 0">
        Aufgaben werden vom <b>Worker-Container</b> abgearbeitet (Docker-Setup). Ohne aktiven Worker bleiben sie „offen".
      </p>
    </div>
  </template>
</template>

<style scoped>
.bgrid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 16px; }
.bgrid .wide { grid-column: 1 / -1; }
@media (max-width: 560px) { .bgrid { grid-template-columns: 1fr; } }

.jrow { border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--paper); padding: 10px 12px; }
.jhead { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.jhead .btn { margin-left: auto; }
.jstat.laeuft { background: var(--accent-tint); color: var(--accent-strong); }
.jstat.fertig { background: var(--success-tint); color: var(--success); }
.jstat.fehler { background: var(--danger-tint, #fde8e6); color: var(--danger, #c4463f); }
.pbar { height: 8px; background: var(--surface-2, var(--surface)); border-radius: var(--radius-pill); overflow: hidden; }
.pfill { height: 100%; background: var(--accent); transition: width 0.3s ease; }
.jlog { white-space: pre-wrap; font-size: 11px; color: var(--ink-2); max-height: 160px; overflow: auto; margin: 6px 0 0; }
</style>
