<script setup>
import { useRoute, useRouter } from 'vue-router'

import AnnotationLayer from '@/components/AnnotationLayer.vue'

const route = useRoute()
const router = useRouter()
const q = route.query

function raus() {
  if (q.werk) router.push({ name: 'werk', params: { id: q.werk } })
  else router.push({ name: 'katalog' })
}
</script>

<template>
  <div class="ne">
    <div class="topbar">
      <button class="btn sm secondary" @click="raus">← Zurück</button>
      <b class="titel">Notizen: {{ q.titel || 'Noten' }}</b>
    </div>
    <div class="body">
      <AnnotationLayer
        v-if="q.ausgabe"
        :ausgabe-id="q.ausgabe"
        :datei-id="q.datei || ''"
        :art="q.art || 'scan_pdf'"
        :seiten="Number(q.seiten) || 1"
        :seite-basis="Number(q.basis) || 0"
      />
      <p v-else class="hint muted">Keine Ausgabe angegeben.</p>
    </div>
  </div>
</template>

<style scoped>
.ne { position: fixed; inset: 0; display: flex; flex-direction: column; background: var(--paper); }
.topbar { display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-bottom: 1px solid var(--border); background: var(--surface); }
.topbar .titel { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.body { flex: 1; min-height: 0; overflow: auto; padding: 14px; width: 100%; max-width: 1100px; margin: 0 auto; }
.hint { padding: 20px; }
</style>
