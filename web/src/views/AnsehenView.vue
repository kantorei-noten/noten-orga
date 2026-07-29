<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api } from '@/api'

const route = useRoute()
const router = useRouter()

const titel = ref(route.query.titel || 'Noten')
const parts = ref([]) // [{ id, name }]
const sel = ref(0)
const src = ref('')
const laden = ref(true)
const fehler = ref('')
const cache = new Map() // dateiId -> objectURL
const startSeite = Number(route.query.seite) || 0 // PDF direkt auf dieser Seite öffnen

// Aktionen für die aktuell gewählte Stimme (Spielmodus/Notizen), datei-genau
const ausgabe = route.query.ausgabe || ''
const basisVon = (i) => Number(i) * 10000
const spielenZiel = computed(() => ({
  name: 'spielen',
  query: { dateien: parts.value[sel.value]?.id, titel: titel.value, werk: route.query.werk, ausgabe, basis: basisVon(sel.value) }
}))
const notizenZiel = computed(() => ({
  name: 'notizen',
  query: {
    datei: parts.value[sel.value]?.id,
    ausgabe,
    titel: parts.value[sel.value]?.name || titel.value,
    werk: route.query.werk,
    basis: basisVon(sel.value),
    art: 'scan_pdf'
  }
}))

// PDF als Blob laden und als Object-URL zurückgeben → nativer PDF-Viewer im iframe
async function ladeBlob(id) {
  if (cache.has(id)) return cache.get(id)
  const res = await fetch(`/api/dateien/${id}/download`, { credentials: 'include' })
  if (!res.ok) throw new Error('Download fehlgeschlagen')
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  cache.set(id, url)
  return url
}

async function zeige(i) {
  sel.value = Number(i)
  laden.value = true
  fehler.value = ''
  try {
    const url = await ladeBlob(parts.value[sel.value].id)
    src.value = startSeite ? `${url}#page=${startSeite}` : url
  } catch {
    fehler.value = 'Diese Datei konnte nicht geladen werden.'
  } finally {
    laden.value = false
  }
}

function raus() {
  if (window.history.length > 1) {
    router.back()
    return
  }
  if (route.query.werk) router.push({ name: 'werk', params: { id: route.query.werk } })
  else router.push({ name: 'katalog' })
}

onMounted(async () => {
  const ids = String(route.query.dateien || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
  const namen = {}
  if (route.query.werk) {
    try {
      const w = await api.get(`/werke/${route.query.werk}`)
      for (const a of w.ausgaben || []) for (const d of a.dateien || []) namen[d.id] = d.original_name
    } catch {
      /* Namen sind optional */
    }
  }
  parts.value = ids.map((id, k) => ({ id, name: namen[id] || `Teil ${k + 1}` }))
  if (parts.value.length) {
    await zeige(Math.min(parts.value.length - 1, Math.max(0, Number(route.query.start) || 0)))
  } else {
    fehler.value = 'Keine Datei angegeben.'
    laden.value = false
  }
})

onUnmounted(() => {
  for (const u of cache.values()) URL.revokeObjectURL(u)
})
</script>

<template>
  <div class="ansehen">
    <div class="topbar">
      <button class="btn sm secondary" @click="raus">← Zurück</button>
      <b class="titel">{{ titel }}</b>
      <select
        v-if="parts.length > 1"
        class="input teil"
        :value="sel"
        @change="(e) => zeige(e.target.value)"
      >
        <option v-for="(p, i) in parts" :key="p.id" :value="i">{{ p.name }}</option>
      </select>
      <RouterLink v-if="ausgabe" class="btn sm secondary" :to="notizenZiel" title="Auf dieser Stimme Notizen machen">Notizen ✎</RouterLink>
      <RouterLink class="btn sm secondary" :to="spielenZiel" title="Diese Stimme im Spielmodus (Blätter-Vollbild)">Spielmodus ▸</RouterLink>
    </div>

    <div class="frame">
      <p v-if="laden" class="hint">Lädt …</p>
      <p v-else-if="fehler" class="hint">{{ fehler }}</p>
      <iframe v-show="!laden && !fehler && src" :src="src" title="Noten-PDF" />
    </div>
  </div>
</template>

<style scoped>
.ansehen {
  position: fixed;
  inset: 0;
  display: flex;
  flex-direction: column;
  background: var(--paper);
}
.topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}
.topbar .titel {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.teil {
  margin-left: auto;
  max-width: 42vw;
}
.frame {
  flex: 1;
  min-height: 0;
  position: relative;
}
.frame iframe {
  width: 100%;
  height: 100%;
  border: 0;
  display: block;
}
.hint {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: var(--ink-2);
}
</style>
