<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api } from '@/api'
import AnnotationLayer from '@/components/AnnotationLayer.vue'
import ChordProEditor from '@/components/ChordProEditor.vue'
import ChordProSheet from '@/components/ChordProSheet.vue'
import VerovioPreview from '@/components/VerovioPreview.vue'
import { erkenneTonart, transponiereAkkord } from '@/lib/chordpro'
import { drucke, sende, speichereDatei } from '@/lib/chordproExport'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const route = useRoute()
const router = useRouter()
const werk = ref(null)
const laden = ref(true)

// Werk-Metadaten bearbeiten / löschen
const metaBearb = ref(false)
const metaEntwurf = ref({})
function metaBearbeiten() {
  const w = werk.value
  metaEntwurf.value = {
    titel: w.titel || '',
    komponist: w.komponist || '',
    textdichter: w.textdichter || '',
    gattung: w.gattung || '',
    entstehungsjahr: w.entstehungsjahr || '',
    notiz: w.notiz || ''
  }
  metaBearb.value = true
}
async function metaSpeichern() {
  const m = metaEntwurf.value
  if (!m.titel.trim()) return
  try {
    await api.patch(`/werke/${route.params.id}`, {
      titel: m.titel.trim(),
      komponist: m.komponist.trim() || null,
      textdichter: m.textdichter.trim() || null,
      gattung: m.gattung.trim() || null,
      entstehungsjahr: m.entstehungsjahr ? Number(m.entstehungsjahr) : null,
      notiz: m.notiz.trim() || null
    })
    werk.value = await api.get(`/werke/${route.params.id}`)
    metaBearb.value = false
  } catch (e) {
    alert('Fehler: ' + e.message)
  }
}
async function werkLoeschen() {
  if (!confirm(`Werk „${werk.value.titel}" mit allen Dateien wirklich löschen? Das kann nicht rückgängig gemacht werden.`)) return
  try {
    await api.del(`/werke/${route.params.id}`)
    router.push('/')
  } catch (e) {
    alert('Fehler: ' + e.message)
  }
}
async function rechteSetzen(a, val) {
  try {
    await api.patch(`/ausgaben/${a.id}`, { rechtestatus: val })
    a.rechtestatus = val
  } catch (e) {
    alert('Fehler: ' + e.message)
  }
}
const annOffen = reactive({})
const hatNotizen = reactive({})
const notizSeiten = reactive({}) // ausgabeId -> [globale Seiten mit Notizen]

async function pruefeNotizen(a) {
  try {
    const r = await api.get(`/ausgaben/${a.id}/annotationen/seiten`)
    notizSeiten[a.id] = r.seiten || []
    hatNotizen[a.id] = (r.seiten || []).length > 0
  } catch {
    /* ignore */
  }
}
// Hat die Datei mit Index di eigene Notizen? (Seiten-Offset = di × 10000)
function hatNotizDatei(a, di) {
  return (notizSeiten[a.id] || []).some((s) => Math.floor(s / 10000) === di)
}
function pruefeAlleNotizen() {
  for (const a of werk.value?.ausgaben || []) {
    if (primaerDatei(a)) pruefeNotizen(a)
  }
}

function toggleAnn(id) {
  annOffen[id] = !annOffen[id]
  // beim Schließen neu prüfen → 'Mit Notizen'-Button erscheint nach dem Speichern
  if (!annOffen[id]) {
    const a = (werk.value?.ausgaben || []).find((x) => x.id === id)
    if (a) pruefeNotizen(a)
  }
}

// PDF-Scans einer Ausgabe (MusicXML wird separat über die Verovio-Ansicht geöffnet)
function pdfDateien(a) {
  return (a.dateien || []).filter((x) => x.art !== 'musicxml')
}
// MusicXML-Dateien (Verovio-Vorschau + transponierbare Ansicht)
function xmlDateien(a) {
  return (a.dateien || []).filter((x) => x.art === 'musicxml')
}
// Anzeigename einer Datei (ohne Endung)
function dateiName(d) {
  return (d.original_name || '').replace(/\.[^.]+$/, '')
}

// ---- Datei-Upload (Drag & Drop / Auswahl) ----
const uploadBusy = reactive({})
const uploadMsg = reactive({})
const dragOver = reactive({})
async function dateienHochladen(a, fileList) {
  const files = Array.from(fileList || []).filter(Boolean)
  if (!files.length) return
  uploadBusy[a.id] = true
  uploadMsg[a.id] = ''
  let ok = 0
  const fehler = []
  for (const f of files) {
    try {
      const fd = new FormData()
      fd.append('file', f)
      fd.append('ausgabe_id', a.id)
      fd.append('art', 'scan_pdf') // XML wird serverseitig als musicxml erkannt
      await api.upload('/dateien', fd)
      ok += 1
    } catch (e) {
      const grund = e?.status === 413 ? ' (zu groß)' : e?.status === 415 ? ' (Format nicht erlaubt)' : ''
      fehler.push(f.name + grund)
    }
  }
  try {
    werk.value = await api.get(`/werke/${route.params.id}`)
    pruefeAlleNotizen()
  } catch {
    /* ignore */
  }
  uploadBusy[a.id] = false
  uploadMsg[a.id] = `${ok} hinzugefügt` + (fehler.length ? ` · Fehler: ${fehler.join(', ')}` : '')
  setTimeout(() => {
    uploadMsg[a.id] = ''
  }, 5000)
}
function onDrop(a, ev) {
  dragOver[a.id] = false
  dateienHochladen(a, ev.dataTransfer && ev.dataTransfer.files)
}
function onPick(a, ev) {
  dateienHochladen(a, ev.target.files)
  ev.target.value = ''
}
async function dateiLoeschen(a, d) {
  if (!window.confirm(`„${dateiName(d) || 'Dieses Blatt'}" wirklich löschen?`)) return
  try {
    await api.del(`/dateien/${d.id}`)
  } catch (e) {
    window.alert(
      e?.status === 409
        ? 'Diese Datei wird noch verwendet (z. B. in einer Setliste) und kann nicht gelöscht werden.'
        : 'Löschen fehlgeschlagen.'
    )
    return
  }
  try {
    werk.value = await api.get(`/werke/${route.params.id}`)
    pruefeAlleNotizen()
  } catch {
    /* ignore */
  }
}
// Bevorzugte Datei für Notizen: PDF-Scan, sonst MusicXML
function primaerDatei(a) {
  return pdfDateien(a)[0] || xmlDateien(a)[0] || null
}
function primaerArt(a) {
  return pdfDateien(a).length ? 'scan_pdf' : 'musicxml'
}

// ---- ChordPro (Text & Akkorde pro Werk) ----
const chordText = ref('')
const chordHalbtoene = ref(0)
const chordEdit = ref(false)
const chordEntwurf = ref('')
const chordStatus = ref('')
const chordTonart = computed(() => erkenneTonart(chordText.value))
const chordAktuell = computed(() =>
  chordTonart.value ? transponiereAkkord(chordTonart.value.label, ((chordHalbtoene.value % 12) + 12) % 12) : null
)
async function ladeChordPro() {
  try {
    chordText.value = (await api.get(`/chordpro/werk/${route.params.id}`)).text || ''
  } catch {
    chordText.value = ''
  }
}
function chordBearbeiten() {
  chordEntwurf.value = chordText.value
  chordEdit.value = true
}
async function chordSpeichern() {
  chordStatus.value = 'Speichern …'
  try {
    await api.put(`/chordpro/werk/${route.params.id}`, { text: chordEntwurf.value })
    chordText.value = chordEntwurf.value
    chordEdit.value = false
    chordStatus.value = 'Gespeichert'
    setTimeout(() => (chordStatus.value = ''), 1500)
  } catch {
    // Editor offen lassen, damit der Text nicht verloren geht
    chordStatus.value = 'Fehler beim Speichern'
  }
}
async function chordAusNoten() {
  chordStatus.value = 'Erzeuge aus den Noten …'
  try {
    const r = await api.post(`/werke/${route.params.id}/chordpro/erzeugen`, {})
    if ((r.text || '').trim()) {
      chordEntwurf.value = r.text
      chordEdit.value = true
      const eng = r.engine === 'music21' ? 'music21' : 'Basis-Analyzer'
      chordStatus.value = `Vorschlag erzeugt (${eng}) – Akkorde bitte prüfen`
    } else {
      chordStatus.value = 'Keine MusicXML-Noten zum Ableiten der Akkorde vorhanden'
    }
  } catch {
    chordStatus.value = 'Erzeugung fehlgeschlagen'
  }
}

// ---- Projektionstext (Liedtext für die Gemeinde-Projektion) ----
const projText = computed(() => werk.value?.projektionstext || '')
const projEdit = ref(false)
const projEntwurf = ref('')
const projStatus = ref('')
function projBearbeiten() {
  projEntwurf.value = projText.value
  projEdit.value = true
}
async function projExtrahieren() {
  projStatus.value = 'Extrahiere aus den Noten …'
  try {
    const r = await api.post(`/werke/${route.params.id}/liedtext/extrahieren`, {})
    projEntwurf.value = r.text || ''
    projEdit.value = true
    projStatus.value = (r.text || '').trim()
      ? 'Vorschlag eingefügt – bitte prüfen und nachputzen'
      : 'In den Noten wurde kein Text gefunden'
  } catch {
    projStatus.value = 'Extraktion fehlgeschlagen'
  }
}
async function projSpeichern() {
  projStatus.value = 'Speichern …'
  try {
    werk.value = await api.put(`/werke/${route.params.id}/liedtext`, { text: projEntwurf.value })
    projEdit.value = false
    projStatus.value = 'Gespeichert'
    setTimeout(() => (projStatus.value = ''), 1500)
  } catch {
    projStatus.value = 'Fehler beim Speichern'
  }
}

// ---- Zu Setliste hinzufügen ----
const setlisten = ref([])
const setlPanel = reactive({})
const setlZiel = reactive({})
const setlDatei = reactive({})
const setlVon = reactive({})
const setlBis = reactive({})
const setlMsg = reactive({})
async function ladeSetlisten() {
  try {
    setlisten.value = await api.get('/setlisten')
  } catch {
    setlisten.value = []
  }
}
async function setlisteHinzu(a) {
  let sid = setlZiel[a.id]
  if (sid === '__neu__') {
    const name = window.prompt('Name der neuen Setliste:')
    if (!name || !name.trim()) return
    try {
      const neu = await api.post('/setlisten', { name: name.trim() })
      setlisten.value = [neu, ...setlisten.value]
      sid = neu.id
      setlZiel[a.id] = sid
    } catch {
      setlMsg[a.id] = 'Setliste konnte nicht angelegt werden.'
      return
    }
  }
  if (!sid) {
    setlMsg[a.id] = 'Bitte eine Setliste wählen.'
    return
  }
  try {
    await api.post(`/setlisten/${sid}/eintraege`, {
      typ: 'werk',
      werk_id: werk.value.id,
      ausgabe_id: a.id,
      datei_id: setlDatei[a.id] || null,
      seite_von: setlVon[a.id] ? Number(setlVon[a.id]) : null,
      seite_bis: setlBis[a.id] ? Number(setlBis[a.id]) : null
    })
    const sl = setlisten.value.find((x) => x.id === sid)
    setlMsg[a.id] = `Zu „${sl?.name || 'Setliste'}" hinzugefügt ✓`
  } catch {
    setlMsg[a.id] = 'Fehler beim Hinzufügen.'
  }
  setTimeout(() => {
    setlMsg[a.id] = ''
  }, 4000)
}

// Ein-Klick-Menü am einzelnen Blatt
const setlMenu = reactive({})
const setlBlattMsg = reactive({})
async function blattZuSetliste(a, d, sid) {
  if (sid === '__neu__') {
    const name = window.prompt('Name der neuen Setliste:')
    if (!name || !name.trim()) return
    try {
      const neu = await api.post('/setlisten', { name: name.trim() })
      setlisten.value = [neu, ...setlisten.value]
      sid = neu.id
    } catch {
      setlBlattMsg[d.id] = 'Fehler'
      return
    }
  }
  try {
    await api.post(`/setlisten/${sid}/eintraege`, {
      typ: 'werk',
      werk_id: werk.value.id,
      ausgabe_id: a.id,
      datei_id: d.id
    })
    const sl = setlisten.value.find((x) => x.id === sid)
    setlBlattMsg[d.id] = `→ „${sl?.name || 'Setliste'}" ✓`
  } catch {
    setlBlattMsg[d.id] = 'Fehler beim Hinzufügen'
  }
  setTimeout(() => {
    setlBlattMsg[d.id] = ''
    setlMenu[d.id] = false
  }, 1800)
}

onMounted(async () => {
  try {
    werk.value = await api.get(`/werke/${route.params.id}`)
    await ladeChordPro()
    pruefeAlleNotizen()
    ladeSetlisten()
  } finally {
    laden.value = false
  }
})
</script>

<template>
  <p v-if="laden" class="muted">Lädt …</p>
  <template v-else-if="werk">
    <RouterLink to="/" class="muted" style="font-size: var(--text-sm)">← Katalog</RouterLink>
    <div class="toolbar" style="margin-top: 8px">
      <h1 style="margin: 0; flex: 1">{{ werk.titel }}</h1>
      <button v-if="auth.darfSchreiben" class="btn sm ghost" @click="metaBearbeiten">Bearbeiten ✎</button>
      <button v-if="auth.darfSchreiben" class="btn sm ghost" @click="werkLoeschen">Löschen</button>
    </div>
    <p class="muted">{{ werk.komponist || '—' }}<template v-if="werk.gattung"> · {{ werk.gattung }}</template></p>

    <div v-if="metaBearb" class="card" style="margin: 10px 0">
      <b>Werk-Metadaten bearbeiten</b>
      <div class="grid2" style="margin-top: 10px">
        <label class="field"><span>Titel *</span><input class="input" v-model="metaEntwurf.titel" /></label>
        <label class="field"><span>Komponist</span><input class="input" v-model="metaEntwurf.komponist" /></label>
        <label class="field"><span>Textdichter</span><input class="input" v-model="metaEntwurf.textdichter" /></label>
        <label class="field"><span>Gattung</span><input class="input" v-model="metaEntwurf.gattung" placeholder="Choral, Motette …" /></label>
        <label class="field"><span>Entstehungsjahr</span><input class="input" type="number" v-model="metaEntwurf.entstehungsjahr" /></label>
        <label class="field"><span>Notiz</span><input class="input" v-model="metaEntwurf.notiz" /></label>
      </div>
      <div class="toolbar" style="margin-top: 10px">
        <button class="btn sm primary" :disabled="!metaEntwurf.titel.trim()" @click="metaSpeichern">Speichern</button>
        <button class="btn sm ghost" @click="metaBearb = false">Abbrechen</button>
      </div>
    </div>
    <div class="stack" style="margin: 12px 0">
      <div>
        <span v-for="g in werk.gesangbuch" :key="g.buch + g.nummer" class="tag" style="margin-right: 6px">
          {{ g.buch }} {{ g.nummer }}
        </span>
        <span v-for="t in werk.tags" :key="t" class="tag" style="margin-right: 6px">{{ t }}</span>
      </div>
    </div>
    <div class="card">
      <b>Ausgaben &amp; Dateien</b>
      <div class="stack" style="margin-top: 10px">
        <div v-for="a in werk.ausgaben" :key="a.id">
          <div class="row">
            <div class="main">
              <b>{{ a.name || 'Ausgabe' }}</b>
              <div class="sub">
                {{ a.besetzung || '—' }}<template v-if="a.tonart"> · {{ a.tonart }}</template>
                · {{ a.dateien.length }} Datei(en)
              </div>
            </div>
            <RouterLink
              v-if="pdfDateien(a).length"
              class="btn sm primary"
              :to="{ name: 'ansehen', query: { dateien: pdfDateien(a).map((x) => x.id).join(','), ausgabe: a.id, titel: werk.titel, werk: werk.id } }"
            >Ansehen ▸</RouterLink>
            <RouterLink
              v-if="pdfDateien(a).length === 1"
              class="btn sm secondary"
              :to="{ name: 'spielen', query: { dateien: pdfDateien(a).map((x) => x.id).join(','), titel: werk.titel, werk: werk.id, ausgabe: a.id } }"
            >Spielmodus ▸</RouterLink>
            <RouterLink
              v-if="hatNotizen[a.id] && pdfDateien(a).length <= 1"
              class="btn sm secondary"
              :to="{ name: 'notizblatt', query: { datei: primaerDatei(a)?.id, ausgabe: a.id, titel: werk.titel, werk: werk.id, art: primaerArt(a) } }"
            >Mit Notizen ▸</RouterLink>
            <RouterLink
              v-for="d in a.dateien.filter((x) => x.art === 'musicxml')"
              :key="d.id"
              class="btn sm secondary"
              :to="{ name: 'noten', params: { dateiId: d.id } }"
            >Noten ▸</RouterLink>
            <button v-if="auth.darfSchreiben && primaerDatei(a) && pdfDateien(a).length <= 1" class="btn sm ghost" @click="toggleAnn(a.id)">Notizen ✎</button>
            <button v-if="auth.darfSchreiben" class="btn sm ghost" @click="setlPanel[a.id] = !setlPanel[a.id]">＋ Zu Setliste</button>
            <select
              v-if="auth.darfSchreiben"
              class="rechte"
              :class="a.rechtestatus === 'public_domain' || a.rechtestatus === 'lizenziert' ? 'ok' : 'warn'"
              :value="a.rechtestatus"
              title="Rechtestatus (steuert, ob gebündelt/gedruckt werden darf)"
              @change="rechteSetzen(a, $event.target.value)"
            >
              <option value="public_domain">gemeinfrei</option>
              <option value="lizenziert">lizenziert</option>
              <option value="unbekannt">unbekannt</option>
              <option value="gesperrt">gesperrt</option>
            </select>
            <span v-else class="badge" :class="a.rechtestatus === 'public_domain' ? 'ok' : 'warn'">
              {{ a.rechtestatus }}
            </span>
          </div>
          <div v-if="auth.darfSchreiben && setlPanel[a.id]" class="setlpanel">
            <label class="sp-f"><span>Blatt</span>
              <select class="input" v-model="setlDatei[a.id]">
                <option value="">Ganzes Werk (bevorzugtes Blatt)</option>
                <option v-for="(d, di) in pdfDateien(a)" :key="d.id" :value="d.id">{{ (dateiName(d) || ('Blatt ' + (di + 1))) + (d.seiten > 1 ? ` (${d.seiten} Seiten)` : '') }}</option>
              </select>
            </label>
            <label class="sp-f"><span>Seiten (optional)</span>
              <span style="display: flex; gap: 4px">
                <input class="input" type="number" min="1" style="width: 68px" v-model="setlVon[a.id]" placeholder="von" />
                <input class="input" type="number" min="1" style="width: 68px" v-model="setlBis[a.id]" placeholder="bis" />
              </span>
            </label>
            <label class="sp-f"><span>Setliste</span>
              <select class="input" v-model="setlZiel[a.id]">
                <option value="">– wählen –</option>
                <option v-for="sl in setlisten" :key="sl.id" :value="sl.id">{{ sl.name }}</option>
                <option value="__neu__">＋ Neue Setliste …</option>
              </select>
            </label>
            <button class="btn sm primary" @click="setlisteHinzu(a)">Hinzufügen</button>
            <span class="muted" style="font-size: 12px">{{ setlMsg[a.id] }}</span>
          </div>
          <div v-if="pdfDateien(a).length" class="thumbs">
            <div v-for="(d, di) in pdfDateien(a)" :key="d.id" class="thumbcard">
              <RouterLink
                class="thumb"
                :to="{ name: 'ansehen', query: { dateien: pdfDateien(a).map((x) => x.id).join(','), start: di, ausgabe: a.id, titel: werk.titel, werk: werk.id } }"
              >
                <img
                  :src="`/api/dateien/${d.id}/thumbnail`"
                  loading="lazy"
                  alt="Vorschau"
                  @error="(e) => { const c = e.target.closest('.thumbcard'); if (c) c.style.display = 'none' }"
                />
              </RouterLink>
              <div class="thumbname" :title="d.original_name || ''">{{ dateiName(d) || ('Blatt ' + (di + 1)) }}<template v-if="d.seiten > 1"> · {{ d.seiten }} Seiten</template></div>
              <div class="thumbacts">
                <RouterLink
                  class="ta"
                  :to="{ name: 'ansehen', query: { dateien: pdfDateien(a).map((x) => x.id).join(','), start: di, ausgabe: a.id, titel: werk.titel, werk: werk.id } }"
                >Ansehen</RouterLink>
                <RouterLink
                  class="ta"
                  :to="{ name: 'spielen', query: { dateien: d.id, titel: werk.titel, werk: werk.id, ausgabe: a.id, basis: di * 10000 } }"
                >Spielen</RouterLink>
                <RouterLink
                  v-if="auth.darfSchreiben"
                  class="ta"
                  :class="{ 'ta-hat': hatNotizDatei(a, di) }"
                  :to="{ name: 'notizen', query: { datei: d.id, ausgabe: a.id, titel: d.original_name || werk.titel, werk: werk.id, basis: di * 10000, art: 'scan_pdf' } }"
                >{{ hatNotizDatei(a, di) ? '● Notizen' : 'Notizen' }}</RouterLink>
                <button v-if="auth.darfSchreiben" class="ta ta-del" @click="dateiLoeschen(a, d)">Löschen</button>
                <span v-if="auth.darfSchreiben" class="ta-menu">
                  <button class="ta" @click="setlMenu[d.id] = !setlMenu[d.id]">Setliste ▾</button>
                  <div v-if="setlMenu[d.id]" class="ta-dropdown">
                    <button v-for="sl in setlisten" :key="sl.id" class="dd-item" @click="blattZuSetliste(a, d, sl.id)">{{ sl.name }}</button>
                    <button class="dd-item dd-neu" @click="blattZuSetliste(a, d, '__neu__')">＋ Neue Setliste …</button>
                    <div v-if="setlBlattMsg[d.id]" class="dd-msg">{{ setlBlattMsg[d.id] }}</div>
                  </div>
                </span>
              </div>
            </div>
          </div>
          <div v-if="xmlDateien(a).length" class="thumbs">
            <RouterLink
              v-for="d in xmlDateien(a)"
              :key="d.id"
              class="thumb thumb-xml"
              :to="{ name: 'noten', params: { dateiId: d.id } }"
              title="Noten ansehen &amp; transponieren"
            >
              <VerovioPreview :datei-id="d.id" />
              <span class="thumb-cap">Noten ansehen ▸</span>
            </RouterLink>
          </div>
          <AnnotationLayer
            v-if="annOffen[a.id]"
            :ausgabe-id="a.id"
            :datei-id="primaerDatei(a)?.id || ''"
            :art="primaerArt(a)"
            :seiten="primaerDatei(a)?.seiten || 1"
            style="margin: 8px 0 4px"
          />
          <div
            v-if="auth.darfSchreiben"
            class="uploadzone"
            :class="{ over: dragOver[a.id] }"
            @dragover.prevent="dragOver[a.id] = true"
            @dragleave="dragOver[a.id] = false"
            @drop.prevent="onDrop(a, $event)"
          >
            <label class="ul-label">
              <input
                type="file"
                multiple
                accept="application/pdf,.musicxml,.mxl,.xml"
                style="display: none"
                :disabled="uploadBusy[a.id]"
                @change="onPick(a, $event)"
              />
              ＋ Dateien hinzufügen
            </label>
            <span class="ul-hint">oder Dateien hierher ziehen (PDF / MusicXML)</span>
            <span v-if="uploadBusy[a.id]" class="muted">· Lädt hoch …</span>
            <span v-else-if="uploadMsg[a.id]" class="muted">· {{ uploadMsg[a.id] }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Text & Akkorde (ChordPro) -->
    <div v-if="chordText || auth.darfSchreiben" class="card" style="margin-top: 16px">
      <div class="row" style="align-items: center; gap: 6px">
        <b style="flex: 1">Text &amp; Akkorde (ChordPro)</b>
        <button
          v-if="auth.darfSchreiben && !chordEdit"
          class="btn sm secondary"
          title="Akkorde aus den MusicXML-Noten ableiten (Vorschlag)"
          @click="chordAusNoten"
        >
          Aus Noten erzeugen
        </button>
        <template v-if="chordText && !chordEdit">
          <span class="muted" style="font-size: 12px">Halbtöne</span>
          <button class="btn sm secondary" @click="chordHalbtoene = Math.max(-11, chordHalbtoene - 1)">−</button>
          <b style="min-width: 32px; text-align: center; font-variant-numeric: tabular-nums">
            {{ chordHalbtoene > 0 ? '+' : '' }}{{ chordHalbtoene }}
          </b>
          <button class="btn sm secondary" @click="chordHalbtoene = Math.min(11, chordHalbtoene + 1)">+</button>
          <button class="btn sm ghost" @click="chordHalbtoene = 0">0</button>
          <button v-if="auth.darfSchreiben" class="btn sm ghost" @click="chordBearbeiten">Bearbeiten ✎</button>
          <button class="btn sm ghost" title="Drucken / als PDF" @click="drucke(chordText, chordHalbtoene, werk.titel)">Drucken</button>
          <button class="btn sm ghost" title="Als Datei speichern" @click="speichereDatei(chordText, werk.titel)">Speichern</button>
          <button class="btn sm ghost" title="Versenden" @click="sende(chordText, werk.titel)">Senden</button>
        </template>
      </div>
      <p class="muted hilfe">
        Akkorde stehen in eckigen Klammern direkt vor der Silbe, z.&nbsp;B. <code>[G]Amazing [C]grace</code> —
        unten werden sie <b>über den Silben</b> angezeigt. Beim <b>Bearbeiten</b> musst du die Syntax nicht
        tippen: nutze die <b>Token</b> (anklicken oder hineinziehen), Akkorde/Angaben werden farbig markiert.
        Mit <b>Halbtöne −/+</b> transponierst du alles auf einmal; das Ergebnis lässt sich
        <b>drucken, speichern und versenden</b>.
      </p>

      <template v-if="chordEdit">
        <ChordProEditor v-model="chordEntwurf" />
        <div class="toolbar" style="margin-top: 8px">
          <button class="btn sm primary" @click="chordSpeichern">Speichern</button>
          <button class="btn sm ghost" @click="chordEdit = false">Abbrechen</button>
          <span class="muted">{{ chordStatus }}</span>
        </div>
      </template>
      <template v-else-if="chordText">
        <p v-if="chordTonart" class="muted" style="font-size: 12px; margin: 4px 0 10px">
          Tonart<template v-if="!chordTonart.angegeben"> (vermutlich)</template>: <b>{{ chordTonart.label }}</b>
          <template v-if="chordHalbtoene !== 0"> → <b>{{ chordAktuell }}</b></template>
        </p>
        <ChordProSheet :text="chordText" :halbtoene="chordHalbtoene" />
      </template>
      <p v-else class="muted" style="margin-top: 4px">
        Noch kein ChordPro-Text hinterlegt. <a href="#" @click.prevent="chordBearbeiten">Hinzufügen ✎</a>
      </p>
    </div>

    <!-- Projektionstext (Liedtext für die Gemeinde-Projektion) -->
    <div v-if="projText || auth.darfSchreiben" class="card" style="margin-top: 16px">
      <div class="row" style="align-items: center; gap: 6px">
        <b style="flex: 1">Projektionstext (Gemeinde)</b>
        <template v-if="auth.darfSchreiben && !projEdit">
          <button class="btn sm secondary" @click="projExtrahieren">Aus Noten extrahieren</button>
          <button v-if="projText" class="btn sm ghost" @click="projBearbeiten">Bearbeiten ✎</button>
        </template>
      </div>
      <p class="muted hilfe">
        Der aus den Notenblättern gezogene Liedtext für die <b>Gemeinde-Projektion</b> am Beamer.
        Die Extraktion ist ein <b>Vorschlag</b> – Kopfzeilen, Komponistennamen oder Wiederholungen
        bitte kurz nachputzen. In der <b>Projektion</b> erscheint er dann im Modus „Liedtext".
      </p>

      <template v-if="projEdit">
        <textarea
          v-model="projEntwurf"
          class="input"
          rows="12"
          style="width: 100%; font-family: inherit; line-height: 1.5"
          placeholder="Liedtext … (leere Zeile = neue Folie)"
        />
        <div class="toolbar" style="margin-top: 8px">
          <button class="btn sm primary" @click="projSpeichern">Speichern</button>
          <button class="btn sm ghost" @click="projEdit = false">Abbrechen</button>
          <button class="btn sm secondary" @click="projExtrahieren">Neu aus Noten</button>
          <span class="muted">{{ projStatus }}</span>
        </div>
      </template>
      <template v-else-if="projText">
        <pre class="liedtext">{{ projText }}</pre>
        <span v-if="projStatus" class="muted" style="font-size: 12px">{{ projStatus }}</span>
      </template>
      <p v-else class="muted" style="margin-top: 4px">
        Noch kein Projektionstext.
        <a href="#" @click.prevent="projExtrahieren">Aus Noten extrahieren</a>
        <span class="muted"> {{ projStatus }}</span>
      </p>
    </div>
  </template>
  <div v-else class="empty">Werk nicht gefunden.</div>
</template>

<style scoped>
.liedtext { white-space: pre-wrap; font-family: inherit; margin: 6px 0 0; line-height: 1.55; color: var(--ink); }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 16px; }
@media (max-width: 640px) { .grid2 { grid-template-columns: 1fr; } }
.rechte { font-size: 12px; padding: 3px 8px; border-radius: var(--radius-pill); border: 1px solid var(--border); background: var(--paper); cursor: pointer; }
.rechte.ok { border-color: var(--success); color: var(--success); }
.rechte.warn { border-color: var(--warning, #c07a2b); color: var(--warning, #c07a2b); }
.thumbs { display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0 2px; }
.thumb {
  display: block;
  width: 108px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--paper);
  box-shadow: var(--shadow-1);
  transition: box-shadow 120ms var(--ease-standard), transform 120ms var(--ease-standard);
}
.thumb:hover { box-shadow: var(--shadow-2); transform: translateY(-2px); }
.thumb img { display: block; width: 100%; height: auto; }
.thumbcard { width: 112px; display: flex; flex-direction: column; gap: 3px; }
.thumbcard .thumb { width: 100%; }
.thumbname { font-size: 11px; color: var(--ink-2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.thumbacts { display: flex; flex-wrap: wrap; gap: 1px 8px; }
.ta { font-size: 11px; color: var(--accent); text-decoration: none; cursor: pointer; }
.ta:hover { text-decoration: underline; }
button.ta { border: none; background: none; padding: 0; font-family: inherit; }
.ta-del { color: #c4463f; }
.ta-hat { color: #2e9e5b; font-weight: 700; }
.uploadzone { margin: 12px 0 2px; padding: 10px 12px; border: 1px dashed var(--border-strong); border-radius: var(--radius-md); display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 13px; }
.uploadzone.over { border-color: var(--accent); background: var(--accent-tint); }
.ul-label { cursor: pointer; color: var(--accent); font-weight: 600; }
.ul-hint { color: var(--ink-2); }
.setlpanel { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 10px; margin: 8px 0 2px; padding: 10px 12px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-md); }
.sp-f { display: flex; flex-direction: column; gap: 2px; font-size: 12px; color: var(--ink-2); }
.sp-f .input { min-width: 190px; }
.ta-menu { position: relative; display: inline-block; }
.ta-dropdown { position: absolute; z-index: 10; top: 100%; left: 0; margin-top: 2px; min-width: 180px; max-height: 240px; overflow: auto; background: var(--paper); border: 1px solid var(--border); border-radius: var(--radius-sm); box-shadow: var(--shadow-2); padding: 4px; }
.dd-item { display: block; width: 100%; text-align: left; border: none; background: none; font: inherit; font-size: 12px; padding: 4px 8px; border-radius: 4px; cursor: pointer; color: var(--ink); white-space: nowrap; }
.dd-item:hover { background: var(--surface); }
.dd-neu { color: var(--accent); }
.dd-msg { font-size: 11px; color: var(--accent-strong); padding: 4px 8px; }
.thumb-xml { width: 264px; }
.thumb-xml :deep(.vp) { max-height: 156px; overflow: hidden; background: #fff; }
.thumb-cap { display: block; font-size: 11px; color: var(--accent); padding: 4px 8px; border-top: 1px solid var(--border); background: var(--paper); }
.hilfe { max-width: 72ch; margin: 6px 0 12px; line-height: 1.5; font-size: 13px; }
.hilfe code { background: var(--surface); border: 1px solid var(--border); border-radius: 5px; padding: 0 4px; font-size: 0.92em; }
.cp-edit { width: 100%; min-height: 220px; font-family: var(--font-mono); font-size: 13px; white-space: pre; }
</style>
