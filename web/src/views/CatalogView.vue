<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api } from '@/api'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const router = useRouter()
const werke = ref([])
const laden = ref(true)
const suchbegriff = ref('')

const ansicht = ref('liste') // 'liste' | 'baum'
const gruppierung = ref('komponist') // 'komponist' | 'gattung' | 'anlass'
const baum = ref([])
const baumLaedt = ref(false)
const offen = ref(new Set())

onMounted(async () => {
  try {
    werke.value = await api.get('/werke?limit=100')
  } finally {
    laden.value = false
  }
})

function suchen() {
  if (suchbegriff.value.trim()) {
    router.push({ name: 'suche', query: { q: suchbegriff.value.trim() } })
  }
}

async function ladeBaum() {
  baumLaedt.value = true
  offen.value = new Set()
  try {
    baum.value = await api.get('/werke/baum?feld=' + gruppierung.value)
  } catch {
    baum.value = []
  } finally {
    baumLaedt.value = false
  }
}
function zeigeBaum() {
  ansicht.value = 'baum'
  if (!baum.value.length) ladeBaum()
}
function toggleGruppe(g) {
  const s = new Set(offen.value)
  if (s.has(g)) s.delete(g)
  else s.add(g)
  offen.value = s
}
function wechsleGruppierung(g) {
  if (gruppierung.value === g) return
  gruppierung.value = g
  ladeBaum()
}
</script>

<template>
  <h1>Katalog</h1>
  <div class="toolbar">
    <input
      class="input"
      v-model="suchbegriff"
      placeholder="Suchen — Titel, GL/EG-Nr., Komponist …"
      @keyup.enter="suchen"
    />
    <button class="btn secondary" @click="suchen">Suchen</button>
    <RouterLink v-if="auth.darfSchreiben" class="btn primary" to="/erfassen">Neu erfassen</RouterLink>
  </div>

  <div class="toolbar" style="margin-top: 2px">
    <div class="seg">
      <button :class="{ active: ansicht === 'liste' }" @click="ansicht = 'liste'">Liste</button>
      <button :class="{ active: ansicht === 'baum' }" @click="zeigeBaum">Baum</button>
    </div>
    <template v-if="ansicht === 'baum'">
      <span class="muted" style="font-size: var(--text-sm)">gruppiert nach</span>
      <div class="seg">
        <button :class="{ active: gruppierung === 'komponist' }" @click="wechsleGruppierung('komponist')">Komponist</button>
        <button :class="{ active: gruppierung === 'gattung' }" @click="wechsleGruppierung('gattung')">Gattung</button>
        <button :class="{ active: gruppierung === 'anlass' }" @click="wechsleGruppierung('anlass')">Anlass</button>
      </div>
    </template>
  </div>

  <!-- Flache Liste -->
  <template v-if="ansicht === 'liste'">
    <p v-if="laden" class="muted">Lädt …</p>
    <div v-else-if="werke.length === 0" class="empty">
      <b>Noch keine Werke</b>
      <p class="muted" style="margin: 6px 0 0">Lege das erste Stück an oder importiere per CSV.</p>
    </div>
    <div v-else class="stack">
      <RouterLink v-for="w in werke" :key="w.id" class="row" :to="{ name: 'werk', params: { id: w.id } }">
        <div class="main">
          <b>{{ w.titel }}</b>
          <div class="sub">{{ w.komponist || '—' }}<template v-if="w.gattung"> · {{ w.gattung }}</template></div>
        </div>
        <span v-if="w.gesangbuch?.length" class="nums">{{ w.gesangbuch.join(' · ') }}</span>
      </RouterLink>
    </div>
    <p class="muted" style="font-size: 12px; margin-top: 8px">Zeigt die ersten 100 — für den vollen Bestand die Suche oder die Baumansicht nutzen.</p>
  </template>

  <!-- Baumansicht -->
  <template v-else>
    <p v-if="baumLaedt" class="muted">Lädt …</p>
    <div v-else-if="baum.length === 0" class="empty">Keine Einträge.</div>
    <div v-else class="stack">
      <div v-for="g in baum" :key="g.gruppe" class="gruppe">
        <button class="ghead" @click="toggleGruppe(g.gruppe)">
          <span class="caret">{{ offen.has(g.gruppe) ? '▾' : '▸' }}</span>
          <b class="gname">{{ g.gruppe }}</b>
          <span class="anz">{{ g.anzahl }}</span>
        </button>
        <div v-if="offen.has(g.gruppe)" class="kinder">
          <RouterLink v-for="w in g.werke" :key="w.id" class="kind" :to="{ name: 'werk', params: { id: w.id } }">
            {{ w.titel }}
          </RouterLink>
        </div>
      </div>
    </div>
  </template>
</template>

<style scoped>
.seg { display: inline-flex; background: var(--surface-2, var(--surface)); border: 1px solid var(--border); border-radius: var(--radius-pill); padding: 3px; }
.seg button { border: none; background: none; color: var(--ink-2); font: inherit; font-size: 13px; padding: 5px 12px; border-radius: var(--radius-pill); cursor: pointer; }
.seg button.active { background: var(--accent-tint); color: var(--accent-strong); font-weight: 600; }
.nums { color: var(--ink-2); font-size: var(--text-sm); }

.gruppe { border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--paper); overflow: hidden; }
.ghead { display: flex; align-items: center; gap: 10px; width: 100%; text-align: left; background: none; border: none; cursor: pointer; padding: 10px 12px; font: inherit; color: var(--ink); }
.ghead:hover { background: var(--surface); }
.caret { color: var(--ink-2); width: 14px; flex: 0 0 auto; }
.gname { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.anz { flex: 0 0 auto; background: var(--surface-2, var(--surface)); color: var(--ink-2); border-radius: var(--radius-pill); padding: 1px 9px; font-size: 12px; font-variant-numeric: tabular-nums; }
.kinder { display: flex; flex-direction: column; border-top: 1px solid var(--border); }
.kind { padding: 8px 12px 8px 36px; color: var(--ink); text-decoration: none; border-bottom: 1px solid var(--border); }
.kind:last-child { border-bottom: none; }
.kind:hover { background: var(--surface); }
</style>
