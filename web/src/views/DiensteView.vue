<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

import { api } from '@/api'
import DienstDetail from '@/components/DienstDetail.vue'
import { druckeDienstplan } from '@/lib/dienstDruck'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const meine = ref([])
const gruppen = ref([])
const dienste = ref([])
const nutzer = ref([])
const setlisten = ref([])
const laden = ref(true)
const fehler = ref('')

const ARTEN = [
  ['chor', 'Chor'],
  ['blaeser', 'Bläser'],
  ['band', 'Band'],
  ['sonstige', 'Sonstige']
]
function artName(a) {
  return (ARTEN.find((x) => x[0] === a) || [a, a])[1]
}

const neueGruppe = ref({ name: '', art: 'chor' })
const offenGruppe = ref(null)
const mitgliedWahl = ref({})
const neuerDienst = ref({ gruppe_id: '', setliste_id: '', datum: '', notiz: '' })
const meineNotiz = reactive({})

const ansicht = ref('liste') // 'liste' | 'kalender'
const offenDienst = ref(null)

async function load() {
  laden.value = true
  try {
    meine.value = await api.get('/meine-dienste')
    for (const d of meine.value) meineNotiz[d.id] = d.meine_notiz || ''
    if (auth.darfSchreiben) {
      const [g, d, n, s] = await Promise.all([
        api.get('/gruppen'),
        api.get('/dienste'),
        api.get('/benutzer/auswahl'),
        api.get('/setlisten')
      ])
      gruppen.value = g
      dienste.value = d
      nutzer.value = n
      setlisten.value = s
    }
  } catch (e) {
    fehler.value = 'Laden fehlgeschlagen: ' + (e?.message || '')
  } finally {
    laden.value = false
  }
}

// --- Meine Zusagen ---
async function zusagen(d, status) {
  await api.post(`/dienste/${d.id}/zusage`, { status, notiz: (meineNotiz[d.id] || '').trim() || null })
  await load()
}

// --- Gruppen (musiker) ---
async function gruppeAnlegen() {
  if (!neueGruppe.value.name.trim()) return
  await api.post('/gruppen', { name: neueGruppe.value.name.trim(), art: neueGruppe.value.art })
  neueGruppe.value = { name: '', art: 'chor' }
  await load()
}
async function gruppeLoeschen(g) {
  if (!confirm(`Gruppe „${g.name}" löschen? Auch zugehörige Dienste werden entfernt.`)) return
  await api.del(`/gruppen/${g.id}`)
  await load()
}
function nichtMitglieder(g) {
  const ids = new Set((g.mitglieder || []).map((m) => m.id))
  return nutzer.value.filter((u) => !ids.has(u.id))
}
async function mitgliedHinzu(g) {
  const uid = mitgliedWahl.value[g.id]
  if (!uid) return
  await api.post(`/gruppen/${g.id}/mitglieder`, { benutzer_id: uid })
  mitgliedWahl.value[g.id] = ''
  await load()
}
async function mitgliedWeg(g, uid) {
  await api.del(`/gruppen/${g.id}/mitglieder/${uid}`)
  await load()
}

// --- Termin anlegen ---
async function dienstAnlegen() {
  const d = neuerDienst.value
  if (!d.gruppe_id) {
    fehler.value = 'Bitte eine Gruppe wählen.'
    return
  }
  fehler.value = ''
  await api.post('/dienste', {
    gruppe_id: d.gruppe_id,
    setliste_id: d.setliste_id || null,
    datum: d.datum || null,
    notiz: d.notiz.trim() || null
  })
  neuerDienst.value = { gruppe_id: '', setliste_id: '', datum: '', notiz: '' }
  await load()
}

function drucken() {
  druckeDienstplan(dienste.value, gruppen.value)
}

function summary(d) {
  const t = d.teilnehmer || []
  const ja = t.filter((x) => x.status === 'zugesagt').length
  const nein = t.filter((x) => x.status === 'abgesagt').length
  return { ja, nein, offen: t.length - ja - nein, total: t.length }
}

// --- Kalender ---
const heute = new Date()
const kalJahr = ref(heute.getFullYear())
const kalMonat = ref(heute.getMonth())
function iso(dt) {
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`
}
const heuteIso = iso(heute)
const dienstNachDatum = computed(() => {
  const m = {}
  for (const d of dienste.value) if (d.datum) (m[d.datum] ||= []).push(d)
  return m
})
const monatsName = computed(() =>
  new Date(kalJahr.value, kalMonat.value, 1).toLocaleDateString('de-DE', { month: 'long', year: 'numeric' })
)
const wochen = computed(() => {
  const first = new Date(kalJahr.value, kalMonat.value, 1)
  const off = (first.getDay() + 6) % 7 // Montag = Wochenstart
  let cur = new Date(kalJahr.value, kalMonat.value, 1 - off)
  const weeks = []
  for (let w = 0; w < 6; w++) {
    const days = []
    for (let i = 0; i < 7; i++) {
      const k = iso(cur)
      days.push({ iso: k, tag: cur.getDate(), imMonat: cur.getMonth() === kalMonat.value, dienste: dienstNachDatum.value[k] || [] })
      cur = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + 1)
    }
    weeks.push(days)
  }
  return weeks
})
function monatWechsel(delta) {
  let m = kalMonat.value + delta
  let y = kalJahr.value
  if (m < 0) {
    m = 11
    y--
  } else if (m > 11) {
    m = 0
    y++
  }
  kalMonat.value = m
  kalJahr.value = y
}

onMounted(load)
</script>

<template>
  <h1>Dienste</h1>
  <p v-if="fehler" class="error">{{ fehler }}</p>
  <p v-if="laden" class="muted">Lädt …</p>

  <template v-else>
    <!-- Meine Dienste (jede/r Eingetragene) -->
    <template v-if="meine.length">
      <h2>Meine Dienste</h2>
      <p class="muted" style="margin: 0 0 10px">Du bist hier eingetragen — bitte zu- oder absagen.</p>
      <div class="stack" style="margin-bottom: 22px">
        <div v-for="d in meine" :key="d.id" class="mein" :class="d.mein_status">
          <div class="row">
            <div class="main">
              <b>{{ d.datum || 'ohne Datum' }} · {{ d.gruppe_name }}</b>
              <div class="sub">
                <template v-if="d.setliste_name">Setliste: {{ d.setliste_name }} · </template>
                <template v-if="d.notiz">{{ d.notiz }} · </template>
                <span class="stat">{{ d.mein_status === 'zugesagt' ? 'zugesagt ✓' : d.mein_status === 'abgesagt' ? 'abgesagt ✕' : 'noch offen' }}</span>
              </div>
            </div>
            <button class="btn sm" :class="d.mein_status === 'zugesagt' ? 'primary' : 'secondary'" @click="zusagen(d, 'zugesagt')">Ich kann ✓</button>
            <button class="btn sm" :class="d.mein_status === 'abgesagt' ? 'primary' : 'ghost'" @click="zusagen(d, 'abgesagt')">Kann nicht ✕</button>
          </div>
          <input class="input" v-model="meineNotiz[d.id]" placeholder="Notiz (z. B. erst ab 9:30)" style="margin-top: 6px" @keyup.enter="zusagen(d, d.mein_status === 'abgesagt' ? 'abgesagt' : 'zugesagt')" />
        </div>
      </div>
    </template>

    <!-- Verwaltung (musiker) -->
    <template v-if="auth.darfSchreiben">
      <h2>Gruppen</h2>
      <div class="card" style="max-width: 640px; margin-bottom: 12px">
        <div class="toolbar" style="margin: 0; flex-wrap: wrap">
          <input class="input" v-model="neueGruppe.name" placeholder="Name, z. B. Kirchenchor" style="flex: 1; min-width: 140px" @keyup.enter="gruppeAnlegen" />
          <select class="input" v-model="neueGruppe.art" style="max-width: 130px">
            <option v-for="a in ARTEN" :key="a[0]" :value="a[0]">{{ a[1] }}</option>
          </select>
          <button class="btn primary" :disabled="!neueGruppe.name.trim()" @click="gruppeAnlegen">Anlegen</button>
        </div>
      </div>
      <div v-if="gruppen.length" class="stack" style="max-width: 640px; margin-bottom: 22px">
        <div v-for="g in gruppen" :key="g.id" class="gbox">
          <div class="row">
            <div class="main">
              <b>{{ g.name }}</b>
              <div class="sub"><span class="tag">{{ artName(g.art) }}</span> {{ g.anzahl_mitglieder }} Mitglieder</div>
            </div>
            <button class="btn sm ghost" @click="offenGruppe = offenGruppe === g.id ? null : g.id">Mitglieder ▾</button>
            <button class="btn sm ghost" title="Gruppe löschen" @click="gruppeLoeschen(g)">✕</button>
          </div>
          <div v-if="offenGruppe === g.id" class="konfig">
            <div v-for="m in g.mitglieder" :key="m.id" class="mrow"><span>{{ m.benutzername }}</span><button class="btn sm ghost" @click="mitgliedWeg(g, m.id)">✕</button></div>
            <div class="toolbar" style="margin: 8px 0 0">
              <select class="input" v-model="mitgliedWahl[g.id]" style="flex: 1">
                <option value="">Mitglied hinzufügen …</option>
                <option v-for="u in nichtMitglieder(g)" :key="u.id" :value="u.id">{{ u.benutzername }}</option>
              </select>
              <button class="btn sm secondary" :disabled="!mitgliedWahl[g.id]" @click="mitgliedHinzu(g)">+</button>
            </div>
          </div>
        </div>
      </div>

      <div class="toolbar" style="align-items: center">
        <h2 style="margin: 0; flex: 1">Termine</h2>
        <button class="btn sm secondary" title="Dienstplan als Liste drucken" @click="drucken">Drucken</button>
        <div class="seg">
          <button :class="{ active: ansicht === 'liste' }" @click="ansicht = 'liste'">Liste</button>
          <button :class="{ active: ansicht === 'kalender' }" @click="ansicht = 'kalender'">Kalender</button>
        </div>
      </div>

      <div class="card" style="max-width: 640px; margin: 10px 0 14px">
        <div class="stack" style="gap: 8px">
          <select class="input" v-model="neuerDienst.gruppe_id">
            <option value="">Gruppe wählen …</option>
            <option v-for="g in gruppen" :key="g.id" :value="g.id">{{ g.name }}</option>
          </select>
          <select class="input" v-model="neuerDienst.setliste_id">
            <option value="">Setliste (optional) …</option>
            <option v-for="sl in setlisten" :key="sl.id" :value="sl.id">{{ sl.name }}</option>
          </select>
          <div class="toolbar" style="margin: 0">
            <input class="input" type="date" v-model="neuerDienst.datum" />
            <input class="input" v-model="neuerDienst.notiz" placeholder="Notiz (optional)" style="flex: 1" />
            <button class="btn primary" :disabled="!neuerDienst.gruppe_id" @click="dienstAnlegen">Planen</button>
          </div>
        </div>
      </div>

      <!-- Liste -->
      <template v-if="ansicht === 'liste'">
        <div v-if="dienste.length === 0" class="empty">Noch keine Termine.</div>
        <div v-else class="stack">
          <div v-for="d in dienste" :key="d.id" class="gbox">
            <div class="row">
              <div class="main" style="cursor: pointer" @click="offenDienst = offenDienst === d.id ? null : d.id">
                <b>{{ d.datum || 'ohne Datum' }} · {{ d.gruppe_name }}</b>
                <div class="sub">
                  <span class="z ja">✓ {{ summary(d).ja }}</span>
                  <span class="z nein">✕ {{ summary(d).nein }}</span>
                  <span class="z offen">· {{ summary(d).offen }} offen</span>
                  <template v-if="d.setliste_name"> · {{ d.setliste_name }}</template>
                  <template v-if="d.bestaetigt"> · <span class="tag">bestätigt</span></template>
                </div>
              </div>
              <button class="btn sm ghost" @click="offenDienst = offenDienst === d.id ? null : d.id">Details ▾</button>
            </div>
            <div v-if="offenDienst === d.id" class="konfig">
              <DienstDetail :dienst="d" :setlisten="setlisten" :darf-schreiben="auth.darfSchreiben" @reload="load" />
            </div>
          </div>
        </div>
      </template>

      <!-- Kalender -->
      <template v-else>
        <div class="kalkopf">
          <button class="btn sm ghost" @click="monatWechsel(-1)">‹</button>
          <b style="min-width: 180px; text-align: center">{{ monatsName }}</b>
          <button class="btn sm ghost" @click="monatWechsel(1)">›</button>
        </div>
        <div class="kal">
          <div v-for="wt in ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']" :key="wt" class="wt">{{ wt }}</div>
          <template v-for="(week, wi) in wochen" :key="wi">
            <div v-for="tag in week" :key="tag.iso" class="tag-zelle" :class="{ aus: !tag.imMonat, heute: tag.iso === heuteIso }">
              <div class="tnum">{{ tag.tag }}</div>
              <button v-for="d in tag.dienste" :key="d.id" class="chip" :class="{ sel: offenDienst === d.id }" @click="offenDienst = offenDienst === d.id ? null : d.id">
                {{ d.gruppe_name }} <span class="csum">✓{{ summary(d).ja }}</span>
              </button>
            </div>
          </template>
        </div>
        <div v-if="offenDienst && dienste.find((x) => x.id === offenDienst)" class="card" style="margin-top: 12px">
          <b>{{ dienste.find((x) => x.id === offenDienst).datum }} · {{ dienste.find((x) => x.id === offenDienst).gruppe_name }}</b>
          <DienstDetail :dienst="dienste.find((x) => x.id === offenDienst)" :setlisten="setlisten" :darf-schreiben="auth.darfSchreiben" @reload="load" />
        </div>
      </template>
    </template>

    <p v-else-if="!meine.length" class="muted">Du bist aktuell in keinem Dienst eingetragen.</p>
  </template>
</template>

<style scoped>
h2 { font-size: var(--text-lg, 1.15rem); margin: 4px 0 10px; }
.seg { display: inline-flex; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-pill); padding: 3px; }
.seg button { border: none; background: none; color: var(--ink-2); font: inherit; font-size: 13px; padding: 5px 12px; border-radius: var(--radius-pill); cursor: pointer; }
.seg button.active { background: var(--accent-tint); color: var(--accent-strong); font-weight: 600; }

.mein { border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--paper); padding: 10px 12px; border-left: 3px solid var(--border); }
.mein.zugesagt { border-left-color: var(--success); }
.mein.abgesagt { border-left-color: var(--danger, #c4463f); }
.mein .stat { font-weight: 600; }

.gbox { border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--paper); }
.gbox .row { padding: 8px 10px; }
.konfig { padding: 10px 12px; border-top: 1px solid var(--border); background: var(--surface); }
.mrow { display: flex; align-items: center; justify-content: space-between; padding: 3px 0; font-size: var(--text-sm); }
.z { margin-right: 8px; font-variant-numeric: tabular-nums; }
.z.ja { color: var(--success); }
.z.nein { color: var(--danger, #c4463f); }
.z.offen { color: var(--ink-2); }

.kalkopf { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.kal { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
.kal .wt { text-align: center; font-size: 12px; color: var(--ink-2); padding-bottom: 2px; }
.tag-zelle { min-height: 84px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--paper); padding: 3px; display: flex; flex-direction: column; gap: 3px; }
.tag-zelle.aus { background: var(--surface); opacity: 0.55; }
.tag-zelle.heute { border-color: var(--accent); }
.tnum { font-size: 12px; color: var(--ink-2); text-align: right; }
.chip { text-align: left; border: none; background: var(--accent-tint); color: var(--accent-strong); border-radius: 6px; padding: 2px 6px; font-size: 11px; cursor: pointer; line-height: 1.25; }
.chip.sel { outline: 2px solid var(--accent); }
.chip .csum { color: var(--success); font-weight: 700; }
@media (max-width: 640px) { .tag-zelle { min-height: 60px; } .chip { font-size: 10px; } }
</style>
