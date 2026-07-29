<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { api } from '@/api'

const route = useRoute()
const q = ref(route.query.q || '')
const filters = ref({ gattung: null, besetzung: null, rechtestatus: null })
const total = ref(0)
const results = ref([])
const facetten = ref({})
const laden = ref(false)

const DIMS = [
  { key: 'gattung', label: 'Gattung' },
  { key: 'besetzung', label: 'Besetzung' },
  { key: 'rechtestatus', label: 'Rechte' }
]

async function run() {
  laden.value = true
  const p = new URLSearchParams()
  if (q.value.trim()) p.set('q', q.value.trim())
  for (const [k, v] of Object.entries(filters.value)) if (v) p.set(k, v)
  try {
    const data = await api.get('/suche?' + p.toString())
    total.value = data.total
    results.value = data.ergebnisse
    facetten.value = data.facetten
  } finally {
    laden.value = false
  }
}

function toggle(dim, wert) {
  filters.value[dim] = filters.value[dim] === wert ? null : wert
  run()
}

onMounted(run)
</script>

<template>
  <h1>Suche</h1>
  <div class="toolbar">
    <input class="input" v-model="q" placeholder="Titel, GL/EG-Nr., Komponist …" @keyup.enter="run" />
    <button class="btn primary" @click="run">Suchen</button>
  </div>

  <div class="such-layout">
    <aside class="facetten">
      <div v-for="d in DIMS" :key="d.key" class="facet-group">
        <div class="cap">{{ d.label }}</div>
        <div class="facet-chips">
          <button
            v-for="f in facetten[d.key] || []"
            :key="f.wert"
            class="chip"
            :class="{ active: filters[d.key] === f.wert }"
            @click="toggle(d.key, f.wert)"
          >
            {{ f.wert }} <span class="anz">{{ f.anzahl }}</span>
          </button>
        </div>
      </div>
    </aside>

    <section>
      <p class="muted" style="margin-top: 0">{{ laden ? 'Sucht …' : total + ' Treffer' }}</p>
      <div class="stack">
        <RouterLink
          v-for="w in results"
          :key="w.id"
          class="row"
          :to="{ name: 'werk', params: { id: w.id } }"
        >
          <div class="main">
            <b>{{ w.titel }}</b>
            <div class="sub">{{ w.komponist || '—' }}<template v-if="w.gattung"> · {{ w.gattung }}</template></div>
          </div>
          <span v-if="w.gesangbuch?.length" class="nums">{{ w.gesangbuch.join(' · ') }}</span>
        </RouterLink>
      </div>
    </section>
  </div>
</template>

<style scoped>
.such-layout { display: grid; grid-template-columns: 220px 1fr; gap: 24px; }
.facet-group { margin-bottom: 16px; }
.cap { font-size: var(--text-xs); color: var(--ink-3); text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; margin-bottom: 6px; }
.facet-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { display: inline-flex; align-items: center; gap: 6px; height: 30px; padding: 0 11px; border-radius: var(--radius-pill); border: 1px solid var(--border-strong); background: var(--paper); color: var(--ink-2); font: inherit; font-size: var(--text-sm); cursor: pointer; }
.chip.active { background: var(--accent-tint); border-color: var(--accent); color: var(--accent-strong); }
.chip .anz { font-variant-numeric: tabular-nums; font-size: 11px; opacity: 0.8; }
@media (max-width: 700px) { .such-layout { grid-template-columns: 1fr; } }
</style>
