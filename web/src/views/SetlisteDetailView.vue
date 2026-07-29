<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api } from '@/api'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const route = useRoute()
const router = useRouter()
const id = route.params.id
const s = ref(null)
const laden = ref(true)

// Setliste umbenennen / Datum / löschen
const kopfBearb = ref(false)
const kopfName = ref('')
const kopfDatum = ref('')
function kopfBearbeiten() {
  kopfName.value = s.value.name
  kopfDatum.value = s.value.datum || ''
  kopfBearb.value = true
}
async function kopfSpeichern() {
  try {
    s.value = await api.patch(`/setlisten/${id}`, { name: kopfName.value.trim(), datum: kopfDatum.value || null })
    kopfBearb.value = false
  } catch (e) {
    alert('Fehler: ' + e.message)
  }
}
async function setlisteLoeschen() {
  if (!confirm(`Setliste „${s.value.name}" wirklich löschen?`)) return
  try {
    await api.del(`/setlisten/${id}`)
    router.push('/setlisten')
  } catch (e) {
    alert('Fehler: ' + e.message)
  }
}

// Druck: serverseitiges Sammel-PDF (A4/Bundsteg)
const druckPanel = ref(false)
const druckA4 = ref(true)
const druckBundsteg = ref(0)
const druckMsg = ref('')
async function drucken() {
  druckMsg.value = 'Erzeuge PDF …'
  try {
    const params = new URLSearchParams({
      a4: druckA4.value ? 'true' : 'false',
      bundsteg_mm: String(Number(druckBundsteg.value) || 0)
    })
    const res = await fetch(`/api/druck/setliste/${id}?${params}`, { credentials: 'include' })
    if (!res.ok) {
      let d = ''
      try {
        d = (await res.json()).detail
      } catch {
        /* kein JSON */
      }
      druckMsg.value = res.status === 403 ? d || 'Wegen Rechtestatus gesperrt.' : d || 'Keine druckbaren Noten.'
      return
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${(s.value.name || 'setliste').replace(/[^\wäöüÄÖÜß -]+/g, '_')}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    druckMsg.value = ''
    druckPanel.value = false
  } catch {
    druckMsg.value = 'Fehler beim Erzeugen.'
  }
}

const suche = ref('')
const treffer = ref([])
const absTitel = ref('')
function blattName(n) {
  return (n || '').replace(/\.[^.]+$/, '')
}

// Auswahl nach dem Suchen: Blatt + optionaler Seitenbereich
const gewaehlt = ref(null)
const gDatei = ref('')
const gVon = ref('')
const gBis = ref('')

// Bestehenden Eintrag nachträglich bearbeiten (Blatt + Seitenbereich)
const bearb = ref(null)

async function load() {
  try {
    s.value = await api.get(`/setlisten/${id}`)
  } catch {
    s.value = null
  } finally {
    laden.value = false
  }
}

async function werkSuchen() {
  if (!suche.value.trim()) {
    treffer.value = []
    return
  }
  const d = await api.get('/suche?q=' + encodeURIComponent(suche.value.trim()))
  treffer.value = d.ergebnisse.slice(0, 6)
}

async function werkWaehlen(w) {
  try {
    const d = await api.get(`/werke/${w.id}`)
    const aus = (d.ausgaben || [])[0]
    const files = ((aus && aus.dateien) || [])
      .filter((x) => x.art !== 'musicxml')
      .map((x) => ({ id: x.id, name: (x.original_name || '').replace(/\.[^.]+$/, ''), seiten: x.seiten }))
    gewaehlt.value = { werk: d, ausgabe_id: aus ? aus.id : null, files }
  } catch {
    gewaehlt.value = { werk: w, ausgabe_id: null, files: [] }
  }
  gDatei.value = ''
  gVon.value = ''
  gBis.value = ''
  treffer.value = []
  suche.value = ''
}

async function gewaehltHinzu() {
  const g = gewaehlt.value
  if (!g) return
  await api.post(`/setlisten/${id}/eintraege`, {
    typ: 'werk',
    werk_id: g.werk.id,
    ausgabe_id: g.ausgabe_id,
    datei_id: gDatei.value || null,
    seite_von: gVon.value ? Number(gVon.value) : null,
    seite_bis: gBis.value ? Number(gBis.value) : null
  })
  gewaehlt.value = null
  await load()
}

async function abschnittHinzufuegen() {
  if (!absTitel.value.trim()) return
  await api.post(`/setlisten/${id}/eintraege`, {
    typ: 'abschnitt',
    titel: absTitel.value.trim()
  })
  absTitel.value = ''
  await load()
}

async function bearbeiten(e) {
  if (e.typ === 'abschnitt') {
    bearb.value = { eid: e.id, abschnitt: true, titel: e.titel || '' }
    return
  }
  let files = []
  try {
    const d = await api.get(`/werke/${e.werk_id}`)
    const aus = (d.ausgaben || [])[0]
    files = ((aus && aus.dateien) || [])
      .filter((x) => x.art !== 'musicxml')
      .map((x) => ({ id: x.id, name: (x.original_name || '').replace(/\.[^.]+$/, ''), seiten: x.seiten }))
  } catch {
    files = []
  }
  bearb.value = {
    eid: e.id,
    files,
    datei: e.gepinnt_datei_id || '',
    von: e.seite_von || '',
    bis: e.seite_bis || ''
  }
}

async function bearbSpeichern() {
  const b = bearb.value
  if (!b) return
  const body = b.abschnitt
    ? { titel: (b.titel || '').trim() }
    : {
        datei_id: b.datei || null,
        seite_von: b.von ? Number(b.von) : null,
        seite_bis: b.bis ? Number(b.bis) : null
      }
  await api.patch(`/setlisten/${id}/eintraege/${b.eid}`, body)
  bearb.value = null
  await load()
}

// Klick auf einen Werk-Eintrag → das gewählte Blatt (mit Seitenbereich) ansehen
function oeffnen(e) {
  if (e.typ !== 'werk' || !e.datei_id) return
  router.push({
    name: 'ansehen',
    query: {
      dateien: e.datei_id,
      titel: e.werk_titel || '',
      werk: e.werk_id,
      ausgabe: e.aufgeloeste_ausgabe_id || '',
      seite: e.seite_von || 1
    }
  })
}

async function entfernen(eid) {
  await api.del(`/setlisten/${id}/eintraege/${eid}`)
  await load()
}

async function verschieben(idx, dir) {
  const ids = s.value.eintraege.map((e) => e.id)
  const j = idx + dir
  if (j < 0 || j >= ids.length) return
  ;[ids[idx], ids[j]] = [ids[j], ids[idx]]
  s.value = await api.put(`/setlisten/${id}/reihenfolge`, { eintrag_ids: ids })
}

onMounted(load)
</script>

<template>
  <p v-if="laden" class="muted">Lädt …</p>
  <template v-else-if="s">
    <RouterLink to="/setlisten" class="muted" style="font-size: var(--text-sm)">← Setlisten</RouterLink>
    <div class="toolbar" style="margin-top: 8px">
      <h1 style="margin: 0; flex: 1">{{ s.name }}</h1>
      <button v-if="auth.darfSchreiben" class="btn sm ghost" @click="kopfBearbeiten">Umbenennen ✎</button>
      <button v-if="auth.darfSchreiben" class="btn sm ghost" @click="setlisteLoeschen">Löschen</button>
      <button v-if="auth.darfSchreiben" class="btn secondary" @click="druckPanel = !druckPanel">Drucken (PDF)</button>
      <RouterLink class="btn secondary" :to="{ name: 'projektion', params: { setlisteId: s.id } }">Projektion</RouterLink>
      <RouterLink class="btn primary" :to="{ name: 'spielen', params: { setlisteId: s.id } }">Spielen</RouterLink>
    </div>
    <p class="muted">{{ s.datum || 'ohne Datum' }}</p>

    <div v-if="druckPanel" class="card" style="max-width: 560px; margin: 4px 0 8px">
      <b>Setliste als PDF drucken</b>
      <div class="toolbar" style="margin: 8px 0 0; flex-wrap: wrap; gap: 12px; align-items: flex-end">
        <label class="chk"><input type="checkbox" v-model="druckA4" /> Auf A4 normalisieren</label>
        <label class="kf"><span>Bundsteg (mm)</span><input class="input" type="number" min="0" v-model="druckBundsteg" style="width: 90px" /></label>
        <button class="btn sm primary" @click="drucken">PDF erzeugen</button>
        <button class="btn sm ghost" @click="druckPanel = false">Schließen</button>
        <span class="muted">{{ druckMsg }}</span>
      </div>
      <p class="muted" style="font-size: 12px; margin: 6px 0 0">Bundsteg = zusätzlicher innerer Rand zum Binden/Lochen. „A4" vereinheitlicht abweichende Seitengrößen. Gesperrte Rechtestatus-Stücke werden nicht ausgegeben.</p>
    </div>

    <div v-if="kopfBearb" class="card" style="max-width: 560px; margin: 4px 0 8px">
      <div class="toolbar" style="margin: 0; flex-wrap: wrap; gap: 8px; align-items: flex-end">
        <label class="kf"><span>Name</span><input class="input" v-model="kopfName" style="min-width: 200px" /></label>
        <label class="kf"><span>Datum</span><input class="input" type="date" v-model="kopfDatum" /></label>
        <button class="btn sm primary" @click="kopfSpeichern">Speichern</button>
        <button class="btn sm ghost" @click="kopfBearb = false">Abbrechen</button>
      </div>
    </div>

    <div v-if="s.eintraege.length === 0" class="empty" style="margin: 14px 0">Noch keine Einträge.</div>
    <div v-else class="stack" style="margin: 14px 0">
      <div v-for="(e, idx) in s.eintraege" :key="e.id" class="eintrag">
        <div class="row">
          <span class="pos">{{ idx + 1 }}</span>
          <div class="main" :class="{ klick: e.typ === 'werk' && e.datei_id }" @click="oeffnen(e)">
            <b>{{ e.werk_titel || e.titel || '—' }}</b>
            <div class="sub">
              <span class="tag">{{ e.typ === 'abschnitt' ? 'Überschrift' : e.typ }}</span>
              <template v-if="e.blatt_name"> · {{ blattName(e.blatt_name) }}</template>
              <template v-if="e.seite_von"> · Seite {{ e.seite_von }}<template v-if="e.seite_bis && e.seite_bis !== e.seite_von">–{{ e.seite_bis }}</template></template>
              <template v-else-if="e.seiten"> · {{ e.seiten }} Seiten</template>
            </div>
          </div>
          <template v-if="auth.darfSchreiben">
            <button class="btn sm ghost" :title="e.typ === 'abschnitt' ? 'Überschrift umbenennen' : 'Blatt/Seiten bearbeiten'" @click="bearb && bearb.eid === e.id ? (bearb = null) : bearbeiten(e)">✎</button>
            <button class="btn sm ghost" title="nach oben" @click="verschieben(idx, -1)">↑</button>
            <button class="btn sm ghost" title="nach unten" @click="verschieben(idx, 1)">↓</button>
            <button class="btn sm ghost" title="entfernen" @click="entfernen(e.id)">✕</button>
          </template>
        </div>
        <div v-if="bearb && bearb.eid === e.id" class="konfig">
          <div v-if="bearb.abschnitt" class="toolbar" style="gap: 8px; align-items: flex-end; margin: 0">
            <label class="kf"><span>Titel der Überschrift</span><input class="input" v-model="bearb.titel" style="min-width: 220px" @keyup.enter="bearbSpeichern" /></label>
            <button class="btn sm primary" @click="bearbSpeichern">Speichern</button>
            <button class="btn sm ghost" @click="bearb = null">Abbrechen</button>
          </div>
          <div v-else class="toolbar" style="flex-wrap: wrap; gap: 8px; align-items: flex-end; margin: 0">
            <label class="kf"><span>Blatt</span>
              <select class="input" v-model="bearb.datei">
                <option value="">Ganzes Werk (bevorzugtes Blatt)</option>
                <option v-for="(f, i) in bearb.files" :key="f.id" :value="f.id">
                  {{ (f.name || ('Blatt ' + (i + 1))) + (f.seiten > 1 ? ` (${f.seiten} Seiten)` : '') }}
                </option>
              </select>
            </label>
            <label class="kf"><span>Seite von</span><input class="input" type="number" min="1" v-model="bearb.von" style="width: 92px" /></label>
            <label class="kf"><span>Seite bis</span><input class="input" type="number" min="1" v-model="bearb.bis" style="width: 92px" /></label>
            <button class="btn sm ghost" title="ganzes Blatt" @click="bearb.von = ''; bearb.bis = ''">Alle Seiten</button>
            <button class="btn sm primary" @click="bearbSpeichern">Speichern</button>
            <button class="btn sm ghost" @click="bearb = null">Abbrechen</button>
          </div>
          <p v-if="!bearb.abschnitt" class="muted" style="font-size: 12px; margin: 6px 0 0">Seiten leer lassen = ganzes Blatt.</p>
        </div>
      </div>
    </div>

    <div v-if="auth.darfSchreiben" class="grid2">
      <div class="card">
        <b>Werk hinzufügen</b>
        <div class="toolbar" style="margin: 10px 0 0">
          <input class="input" v-model="suche" placeholder="Werk suchen …" @keyup.enter="werkSuchen" />
          <button class="btn secondary" @click="werkSuchen">Suchen</button>
        </div>
        <div class="stack" style="margin-top: 8px">
          <button v-for="w in treffer" :key="w.id" class="row pick" @click="werkWaehlen(w)">
            <div class="main"><b>{{ w.titel }}</b><div class="sub">{{ w.komponist || '—' }}</div></div>
            <span class="plus">+</span>
          </button>
        </div>
        <div v-if="gewaehlt" class="konfig">
          <b>{{ gewaehlt.werk.titel }}</b>
          <span class="muted" style="margin-left: 6px">{{ gewaehlt.werk.komponist || '' }}</span>
          <div class="toolbar" style="margin-top: 8px; flex-wrap: wrap; gap: 8px; align-items: flex-end">
            <label class="kf"><span>Blatt</span>
              <select class="input" v-model="gDatei">
                <option value="">Ganzes Werk (bevorzugtes Blatt)</option>
                <option v-for="(f, i) in gewaehlt.files" :key="f.id" :value="f.id">
                  {{ (f.name || ('Blatt ' + (i + 1))) + (f.seiten > 1 ? ` (${f.seiten} Seiten)` : '') }}
                </option>
              </select>
            </label>
            <label class="kf"><span>Seite von</span><input class="input" type="number" min="1" v-model="gVon" style="width: 92px" /></label>
            <label class="kf"><span>Seite bis</span><input class="input" type="number" min="1" v-model="gBis" style="width: 92px" /></label>
            <button class="btn sm primary" @click="gewaehltHinzu">Hinzufügen</button>
            <button class="btn sm ghost" @click="gewaehlt = null">Abbrechen</button>
          </div>
          <p class="muted" style="font-size: 12px; margin: 6px 0 0">Seiten leer lassen = ganzes Blatt. Bei mehrseitigen Dateien kannst du einen Seitenbereich wählen.</p>
        </div>
      </div>
      <div class="card">
        <b>Zwischenüberschrift</b>
        <p class="muted" style="font-size: 12px; margin: 6px 0 0">Überschrift ohne Noten – gliedert die Setliste und erscheint in der Projektion als eigene Folie (z. B. „Eingang", „Predigt", „Ausgang").</p>
        <label class="field" style="margin-top: 10px"><span>Titel</span>
          <input class="input" v-model="absTitel" placeholder="z. B. Eingang" @keyup.enter="abschnittHinzufuegen" />
        </label>
        <div class="toolbar" style="margin: 0">
          <button class="btn secondary" :disabled="!absTitel.trim()" @click="abschnittHinzufuegen">Hinzufügen</button>
        </div>
      </div>
    </div>
  </template>
  <div v-else class="empty">Setliste nicht gefunden.</div>
</template>

<style scoped>
.pos { flex: 0 0 auto; width: 24px; height: 24px; border-radius: 50%; background: var(--surface-2); color: var(--ink-2); display: flex; align-items: center; justify-content: center; font-size: 12px; font-variant-numeric: tabular-nums; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 640px) { .grid2 { grid-template-columns: 1fr; } }
.pick { width: 100%; border: 1px solid var(--border); background: var(--paper); cursor: pointer; text-align: left; }
.pick:hover { background: var(--surface); }
.plus { font-size: 20px; color: var(--accent); }
.konfig { margin-top: 10px; padding: 10px 12px; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--surface); }
.kf { display: flex; flex-direction: column; gap: 2px; font-size: 12px; color: var(--ink-2); }
.kf .input { min-width: 150px; }
.chk { display: flex; align-items: center; gap: 6px; font-size: var(--text-sm); }
.main.klick { cursor: pointer; }
.main.klick:hover b { text-decoration: underline; }
</style>
