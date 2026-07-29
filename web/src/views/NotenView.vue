<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { druckeSvgSeiten, neuesToolkit, renderMusicXmlSeiten } from '@/lib/verovio'

const route = useRoute()
const svg = ref('')
const semitones = ref(0)
const page = ref(1)
const pageCount = ref(1)
const laden = ref(true)
const fehler = ref('')
const container = ref(null)
const wrap = ref(null)
const vollbild = ref(false)

let tk = null
let rawXml = ''

// Halbton -> Verovio-Intervall (Vorzeichen = Richtung)
const INTERVALS = { 1: 'm2', 2: 'M2', 3: 'm3', 4: 'M3', 5: 'P4', 6: 'd5' }
function intervalFor(s) {
  if (!s) return null
  return (s < 0 ? '-' : '') + (INTERVALS[Math.abs(s)] || 'M2')
}

async function ensureToolkit() {
  if (!tk) tk = await neuesToolkit()
  return tk
}

async function render() {
  const t = await ensureToolkit()
  const w = container.value?.clientWidth || 800
  const opts = {
    scale: vollbild.value ? 55 : 40,
    adjustPageHeight: true,
    breaks: 'auto',
    pageWidth: Math.max(600, Math.floor((w * 100) / 40)),
    header: 'none',
    footer: 'none'
  }
  const iv = intervalFor(semitones.value)
  if (iv) opts.transpose = iv
  t.setOptions(opts)
  t.loadData(rawXml) // Re-Import wendet die Transposition an
  pageCount.value = t.getPageCount() || 1
  if (page.value > pageCount.value) page.value = 1
  svg.value = t.renderToSVG(page.value)
}

function transponiere(d) {
  semitones.value = Math.max(-6, Math.min(6, semitones.value + d))
  render()
}

function zuruecksetzen() {
  semitones.value = 0
  render()
}

function seite(d) {
  const n = page.value + d
  if (n >= 1 && n <= pageCount.value) {
    page.value = n
    svg.value = tk.renderToSVG(n)
  }
}

function toggleVollbild() {
  if (document.fullscreenElement) document.exitFullscreen?.()
  else wrap.value?.requestFullscreen?.().catch(() => {})
}
function onFsChange() {
  vollbild.value = !!document.fullscreenElement
  if (rawXml) render() // größerer Maßstab im Vollbild
}
// Spielansicht: im Vollbild per Tastatur (auch Bluetooth-Fußpedal als Keyboard) blättern
function onKey(e) {
  if (!vollbild.value) return
  if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') {
    e.preventDefault()
    seite(1)
  } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
    e.preventDefault()
    seite(-1)
  }
}
// Tap-Zonen: linkes Drittel zurück, rechtes Drittel vor (nur im Vollbild)
function notenTap(e) {
  if (!vollbild.value || pageCount.value < 2) return
  const r = e.currentTarget.getBoundingClientRect()
  const x = e.clientX - r.left
  if (x < r.width * 0.33) seite(-1)
  else if (x > r.width * 0.67) seite(1)
}

const druckt = ref(false)
async function drucken() {
  druckt.value = true
  try {
    const svgs = await renderMusicXmlSeiten(route.params.dateiId, { transpose: intervalFor(semitones.value) })
    druckeSvgSeiten(svgs, 'Noten')
  } finally {
    druckt.value = false
  }
}

onMounted(async () => {
  document.addEventListener('fullscreenchange', onFsChange)
  window.addEventListener('keydown', onKey)
  try {
    const res = await fetch(`/api/dateien/${route.params.dateiId}/musicxml`, { credentials: 'include' })
    if (!res.ok) throw new Error('MusicXML nicht verfügbar')
    rawXml = await res.text()
    await render()
  } catch {
    fehler.value = 'Noten konnten nicht geladen werden.'
  } finally {
    laden.value = false
  }
})
onUnmounted(() => {
  document.removeEventListener('fullscreenchange', onFsChange)
  window.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div ref="wrap" class="notenwrap" :class="{ voll: vollbild }">
    <div class="toolbar">
      <RouterLink to="/" class="muted" style="font-size: var(--text-sm)">← Katalog</RouterLink>
      <h1 style="flex: 1; margin: 0; font-size: var(--text-lg)">Noten — transponierbar</h1>
      <button class="btn sm secondary" :disabled="druckt || laden" @click="drucken">Drucken</button>
      <button class="btn sm secondary" @click="toggleVollbild">
        {{ vollbild ? 'Spielansicht ✕' : 'Spielansicht ▸' }}
      </button>
    </div>

    <div class="toolbar">
      <span class="muted">Transposition</span>
      <button class="btn sm secondary" @click="transponiere(-1)">−</button>
      <b style="min-width: 76px; text-align: center; font-variant-numeric: tabular-nums">
        {{ semitones > 0 ? '+' : '' }}{{ semitones }} HT
      </b>
      <button class="btn sm secondary" @click="transponiere(1)">+</button>
      <button class="btn sm ghost" @click="zuruecksetzen">Zurücksetzen</button>
      <span style="flex: 1" />
      <template v-if="pageCount > 1">
        <button class="btn sm ghost" @click="seite(-1)">‹</button>
        <span class="muted">{{ page }} / {{ pageCount }}</span>
        <button class="btn sm ghost" @click="seite(1)">›</button>
      </template>
    </div>

    <p v-if="laden" class="muted">Rendert Noten …</p>
    <p v-else-if="fehler" class="error">{{ fehler }}</p>
    <p v-if="vollbild && pageCount > 1" class="muted tapinfo">Tippen: links zurück · rechts vor · (Pfeiltasten/Fußpedal)</p>
    <div ref="container" class="noten" :class="{ tap: vollbild && pageCount > 1 }" @click="notenTap" v-html="svg" />
  </div>
</template>

<style scoped>
.noten { background: #fff; border: 1px solid var(--border); border-radius: var(--radius-md); padding: 10px; overflow: auto; }
.noten :deep(svg) { max-width: 100%; height: auto; }
/* Spielansicht (Vollbild): weiße Fläche, Toolbars bleiben oben erreichbar */
.notenwrap:fullscreen { background: var(--paper); padding: 12px 20px; overflow: auto; }
.notenwrap:fullscreen .toolbar { position: sticky; top: 0; background: var(--paper); z-index: 2; }
.notenwrap:fullscreen .noten { border: none; }
.noten.tap { cursor: pointer; }
.tapinfo { font-size: 12px; margin: 2px 0 6px; text-align: center; }
</style>
