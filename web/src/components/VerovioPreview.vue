<script setup>
import { onMounted, ref } from 'vue'

import { neuesToolkit } from '@/lib/verovio'

const props = defineProps({ dateiId: { type: String, required: true } })
const svg = ref('')
const status = ref('laden') // laden | ok | fehler

onMounted(async () => {
  try {
    const res = await fetch(`/api/dateien/${props.dateiId}/musicxml`, { credentials: 'include' })
    if (!res.ok) throw new Error('nicht verfügbar')
    const xml = await res.text()
    const tk = await neuesToolkit()
    // Feste, flache Seite → renderToSVG(1) zeigt nur die ersten Systeme (Thumbnail).
    tk.setOptions({
      scale: 30,
      adjustPageHeight: false,
      pageHeight: 550,
      pageWidth: 2100,
      breaks: 'auto',
      header: 'none',
      footer: 'none',
      pageMarginTop: 40,
      pageMarginBottom: 0,
      pageMarginLeft: 40,
      pageMarginRight: 40
    })
    tk.loadData(xml)
    svg.value = tk.renderToSVG(1)
    status.value = 'ok'
  } catch {
    status.value = 'fehler'
  }
})
</script>

<template>
  <div class="vp">
    <div v-if="status === 'ok'" class="vp-svg" v-html="svg" />
    <div v-else class="vp-ph">
      <span class="vp-note">♪</span>
      <span>{{ status === 'laden' ? 'Noten …' : 'MusicXML' }}</span>
    </div>
  </div>
</template>

<style scoped>
.vp { width: 100%; }
.vp-svg { width: 100%; }
.vp-svg :deep(svg) { width: 100%; height: auto; display: block; }
.vp-ph {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 4px; min-height: 96px; color: var(--ink-3); font-size: 12px;
}
.vp-note { font-size: 26px; line-height: 1; }
</style>
