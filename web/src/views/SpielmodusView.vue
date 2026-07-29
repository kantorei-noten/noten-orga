<script setup>
import * as pdfjsLib from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api } from '@/api'
import { zeichneAnnotationen } from '@/lib/annotationsDraw'
import { useOnline } from '@/composables/online'

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl

const route = useRoute()
const router = useRouter()
const online = useOnline()

const rootEl = ref(null)
const viewport = ref(null)
const canvas = ref(null)
const canvas2 = ref(null)

const laden = ref(true)
const fehler = ref('')
const setliste = ref(null)
const pageSeq = ref([])
const idx = ref(0)
const half = ref(0)
const halfEnabled = ref(false)
const twoup = ref(false)
const fitWindow = ref(false)
const autoscroll = ref(false)
const scrollY = ref(0)
const showBar = ref(false)
const spielTheme = ref('dark')
const aktTitel = ref('')
const canvasCssH = ref(0)
const vpH = ref(0)

const pdfCache = new Map()
const annCache = new Map()
// Notizen (Annotationen) der Ausgabe je Seite — nur im Einzelwerk-Modus (route.query.ausgabe)
async function annFuer(seite) {
  const aus = route.query.ausgabe
  if (!aus) return null
  if (annCache.has(seite)) return annCache.get(seite)
  let rows = null
  try {
    rows = await api.get(`/ausgaben/${aus}/annotationen?seite=${(Number(route.query.basis) || 0) + seite}`)
  } catch {
    rows = null
  }
  annCache.set(seite, rows)
  return rows
}
let wakeLock = null
let lastTurn = 0
let prevTheme = 'light'
let rafId = 0

const translateY = computed(() =>
  autoscroll.value
    ? -scrollY.value
    : -half.value * Math.max(0, canvasCssH.value - vpH.value)
)

async function ladeResponse(url) {
  try {
    const res = await fetch(url, { credentials: 'include' })
    if (res.ok) return res
  } catch {
    /* offline */
  }
  const cached = 'caches' in window ? await caches.match(url) : null
  if (cached) return cached
  throw new Error('offline und nicht im Zwischenspeicher')
}

async function getPdf(dateiId) {
  if (pdfCache.has(dateiId)) return pdfCache.get(dateiId)
  const res = await ladeResponse(`/api/dateien/${dateiId}/download`)
  const pdf = await pdfjsLib.getDocument({ data: await res.arrayBuffer() }).promise
  pdfCache.set(dateiId, pdf)
  return pdf
}

async function pin() {
  if (!('caches' in window)) return
  try {
    const cache = await caches.open('noten-scans')
    const urls = [...new Set(pageSeq.value.map((x) => `/api/dateien/${x.dateiId}/download`))]
    await Promise.all(
      urls.map(async (u) => {
        if (await cache.match(u)) return
        try {
          const r = await fetch(u, { credentials: 'include' })
          if (r.ok) await cache.put(u, r.clone())
        } catch {
          /* ignore */
        }
      })
    )
  } catch {
    /* ignore */
  }
}

async function build() {
  const seq = []
  for (const e of setliste.value.eintraege) {
    if (!e.datei_id) continue
    const pdf = await getPdf(e.datei_id)
    const von = e.seite_von && e.seite_von >= 1 ? e.seite_von : 1
    const bis = e.seite_bis && e.seite_bis >= von ? Math.min(e.seite_bis, pdf.numPages) : pdf.numPages
    for (let p = von; p <= bis; p++) {
      seq.push({ dateiId: e.datei_id, page: p, titel: e.werk_titel || e.titel || 'Ohne Titel' })
    }
  }
  pageSeq.value = seq
  if (seq.length) await render()
}

// Einzelwerk-Modus: eine oder mehrere Dateien direkt spielen (ohne Setliste)
async function buildDateien(ids, titel) {
  const seq = []
  for (const id of ids) {
    const pdf = await getPdf(id)
    for (let p = 1; p <= pdf.numPages; p++) {
      seq.push({ dateiId: id, page: p, titel })
    }
  }
  pageSeq.value = seq
  if (seq.length) await render()
}

async function renderOne(canvasEl, item, availW, availH) {
  if (!item || !canvasEl) return 0
  const pdf = await getPdf(item.dateiId)
  const page = await pdf.getPage(item.page)
  const base = page.getViewport({ scale: 1 })
  // Auflösung deckeln: Retina bis 2×, aber Canvas nie breiter als 2600px → schont langsame Rechner
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  // Normal an Breite anpassen; im "An Fenster"-Modus die GANZE Seite in die Fensterhöhe
  let cssScale = availW / base.width
  if (fitWindow.value && availH) cssScale = Math.min(availW / base.width, availH / base.height)
  const renderScale = Math.min(cssScale * dpr, 2600 / base.width)
  const vp = page.getViewport({ scale: renderScale })
  // Erst in einen Offscreen-Canvas rendern, dann in einem Rutsch anzeigen → kein Leerblitzen
  const off = document.createElement('canvas')
  off.width = Math.max(1, Math.floor(vp.width))
  off.height = Math.max(1, Math.floor(vp.height))
  const offctx = off.getContext('2d')
  // Weißfläche: die Archiv-PDFs sind gestochene Vektoren mit TRANSPARENTEM Hintergrund →
  // ohne Füllung scheint der dunkle App-Hintergrund durch (schwarze Noten auf Dunkel = unlesbar).
  offctx.fillStyle = '#ffffff'
  offctx.fillRect(0, 0, off.width, off.height)
  await page.render({ canvasContext: offctx, viewport: vp }).promise.catch(() => {})
  const annRows = await annFuer(item.page)
  if (annRows && annRows.length) zeichneAnnotationen(offctx, off.width, off.height, annRows)
  canvasEl.width = off.width
  canvasEl.height = off.height
  // Anzeigegröße EXAKT = tatsächliche Seitengröße (nicht '100%' im Flex → sonst Verzerrung)
  canvasEl.style.width = Math.floor(base.width * cssScale) + 'px'
  canvasEl.style.height = Math.floor(base.height * cssScale) + 'px'
  canvasEl.getContext('2d').drawImage(off, 0, 0)
  return base.height * cssScale
}

function clearCanvas(c) {
  if (!c) return
  c.width = 1
  c.height = 1
  c.style.width = '0px'
  c.style.height = '0px'
}

let rendering = false
let renderPending = false
// Renders serialisieren: nie zwei gleichzeitig (sonst bricht pdf.js ab und hinterlässt
// ein halbes/dunkles Bild — genau das "erst nach mehrmaligem Klicken korrekt"). Letzter gewinnt.
async function render() {
  if (rendering) {
    renderPending = true
    return
  }
  rendering = true
  try {
    await doRender()
  } finally {
    rendering = false
    if (renderPending) {
      renderPending = false
      render()
    }
  }
}

async function doRender() {
  if (!canvas.value || !viewport.value || !pageSeq.value.length) return
  const gap = 12
  const full = viewport.value.clientWidth
  const zwei = twoup.value && idx.value + 1 < pageSeq.value.length
  const availW = twoup.value ? (full - gap) / 2 : full
  const availH = vpH.value || viewport.value.clientHeight
  const h1 = await renderOne(canvas.value, pageSeq.value[idx.value], availW, availH)
  let h2 = 0
  if (canvas2.value) {
    if (zwei) h2 = await renderOne(canvas2.value, pageSeq.value[idx.value + 1], availW, availH)
    else clearCanvas(canvas2.value) // keine zweite Seite → leeren, sonst Geisterbild
  }
  canvasCssH.value = Math.max(h1, h2)
  half.value = 0
  scrollY.value = 0
  aktTitel.value = pageSeq.value[idx.value]?.titel || ''
  const nx = pageSeq.value[idx.value + (twoup.value ? 2 : 1)]
  if (nx) getPdf(nx.dateiId).then((p) => p.getPage(nx.page)).catch(() => {})
}

function schritt() {
  return twoup.value ? 2 : 1
}

function naechste() {
  const now = Date.now()
  if (now - lastTurn < 320) return
  lastTurn = now
  autoscroll.value = false
  if (!twoup.value && halfEnabled.value && half.value === 0 && canvasCssH.value > vpH.value + 4) {
    half.value = 1
    return
  }
  const target = Math.min(pageSeq.value.length - 1, idx.value + schritt())
  if (target !== idx.value) {
    idx.value = target
    render()
  }
}

function vorige() {
  const now = Date.now()
  if (now - lastTurn < 320) return
  lastTurn = now
  autoscroll.value = false
  if (!twoup.value && halfEnabled.value && half.value === 1) {
    half.value = 0
    return
  }
  const target = Math.max(0, idx.value - schritt())
  if (target !== idx.value) {
    idx.value = target
    render()
  }
}

function autoscrollTick() {
  if (!autoscroll.value) return
  scrollY.value += 0.6
  const maxScroll = Math.max(0, canvasCssH.value - vpH.value)
  if (scrollY.value >= maxScroll) {
    scrollY.value = 0
    const target = Math.min(pageSeq.value.length - 1, idx.value + 1)
    if (target !== idx.value) {
      idx.value = target
      render()
    } else {
      autoscroll.value = false
      return
    }
  }
  rafId = requestAnimationFrame(autoscrollTick)
}

function toggleAutoscroll() {
  autoscroll.value = !autoscroll.value
  cancelAnimationFrame(rafId)
  if (autoscroll.value) rafId = requestAnimationFrame(autoscrollTick)
}

function twoupUmschalten() {
  if (twoup.value) {
    autoscroll.value = false
    idx.value = idx.value - (idx.value % 2) // auf gerade Seite → Doppelseiten 0-1, 2-3 …
  }
  render()
}

function onKey(e) {
  if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') {
    e.preventDefault()
    naechste()
  } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
    e.preventDefault()
    vorige()
  } else if (e.key === 'Escape') {
    raus()
  }
}

function measure() {
  vpH.value = viewport.value?.clientHeight || window.innerHeight
}

let resizeTimer = 0
function onResize() {
  clearTimeout(resizeTimer)
  resizeTimer = setTimeout(() => {
    measure()
    if (pageSeq.value.length) render()
  }, 140)
}

function toggleBar() {
  showBar.value = !showBar.value
}

function toggleFullscreen() {
  if (!document.fullscreenElement) rootEl.value?.requestFullscreen?.()
  else document.exitFullscreen?.()
}

async function acquireWake() {
  try {
    wakeLock = await navigator.wakeLock?.request('screen')
  } catch {
    /* nicht verfügbar */
  }
}

function onVisibility() {
  if (document.visibilityState === 'visible') acquireWake()
}

function raus() {
  if (setliste.value) router.push({ name: 'setliste', params: { id: setliste.value.id } })
  else if (route.query.werk) router.push({ name: 'werk', params: { id: route.query.werk } })
  else router.push({ name: 'katalog' })
}

watch(spielTheme, (t) => {
  document.documentElement.dataset.theme = t
})

onMounted(async () => {
  prevTheme = document.documentElement.dataset.theme || 'light'
  document.documentElement.dataset.theme = spielTheme.value
  window.addEventListener('keydown', onKey)
  window.addEventListener('resize', onResize)
  document.addEventListener('visibilitychange', onVisibility)
  await acquireWake()
  try {
    const sid = route.params.setlisteId
    if (sid) {
      setliste.value = await api.get(`/setlisten/${sid}`)
      await nextTick()
      measure()
      await build()
    } else if (route.query.dateien) {
      const ids = String(route.query.dateien).split(',').filter(Boolean)
      await nextTick()
      measure()
      await buildDateien(ids, route.query.titel || 'Noten')
    } else {
      throw new Error('nichts zu spielen')
    }
    pin()
  } catch {
    fehler.value = 'Noten konnten nicht geladen werden.'
  } finally {
    laden.value = false
  }
  // Erst JETZT ist der Canvas im DOM (v-if=laden war vorher aktiv) → jetzt real zeichnen.
  await nextTick()
  measure()
  if (pageSeq.value.length) await render()
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('resize', onResize)
  document.removeEventListener('visibilitychange', onVisibility)
  cancelAnimationFrame(rafId)
  try { wakeLock?.release?.() } catch { /* ignore */ }
  document.documentElement.dataset.theme = prevTheme
})
</script>

<template>
  <div class="spielmodus" ref="rootEl">
    <div v-if="laden" class="center">Lädt Noten …</div>

    <div v-else-if="fehler" class="center">
      <p>{{ fehler }}</p>
      <button class="btn secondary" @click="raus">Zurück</button>
    </div>

    <template v-else-if="pageSeq.length">
      <div class="viewport" ref="viewport">
        <div class="pages" :class="{ twoup }">
          <canvas ref="canvas" class="page" :style="{ transform: twoup ? '' : `translateY(${translateY}px)` }" />
          <canvas ref="canvas2" v-show="twoup" class="page" />
        </div>
      </div>

      <div class="zone left" @click="vorige" />
      <div class="zone center" @click="toggleBar" />
      <div class="zone right" @click="naechste" />

      <div class="pill">
        {{ aktTitel }} · Seite {{ idx + 1 }} / {{ pageSeq.length }}
        <span v-if="twoup"> · 2 Seiten</span>
        <span v-else-if="halfEnabled"> · Halbseite</span>
        <span v-if="!online" class="off"> · offline</span>
      </div>

      <div v-if="showBar" class="bar">
        <button class="btn secondary" @click="raus">✕ Ende</button>
        <label class="chk"><input type="checkbox" v-model="fitWindow" @change="render" /> An Fenster</label>
        <label class="chk"><input type="checkbox" v-model="halfEnabled" :disabled="twoup || fitWindow" /> Halbseite</label>
        <label class="chk"><input type="checkbox" v-model="twoup" @change="twoupUmschalten" /> Zwei Seiten</label>
        <label class="chk"><input type="checkbox" :checked="autoscroll" :disabled="twoup || fitWindow" @change="toggleAutoscroll" /> Auto-Scroll</label>
        <div class="seg">
          <button :class="{ active: spielTheme === 'dark' }" @click="spielTheme = 'dark'">Dunkel</button>
          <button :class="{ active: spielTheme === 'rot' }" @click="spielTheme = 'rot'">Rotlicht</button>
        </div>
        <button class="btn secondary" @click="toggleFullscreen">Vollbild</button>
      </div>
    </template>

    <div v-else class="center">
      <p>Diese Setliste hat keine anzeigbaren Noten (noch keine Scans hochgeladen).</p>
      <button class="btn secondary" @click="raus">Zurück</button>
    </div>
  </div>
</template>

<style scoped>
.spielmodus { position: fixed; inset: 0; background: var(--paper); color: var(--ink); overflow: hidden; }
.center { height: 100%; display: flex; flex-direction: column; gap: 14px; align-items: center; justify-content: center; }
.viewport { position: absolute; inset: 0; overflow: hidden; }
.pages { width: 100%; display: flex; gap: 12px; align-items: flex-start; justify-content: center; }
.pages .page { flex: 0 0 auto; }
.page { display: block; background: #fff; will-change: transform; transition: transform 120ms var(--ease-standard); }
.zone { position: absolute; top: 0; bottom: 0; cursor: pointer; }
.zone.left { left: 0; width: 33%; }
.zone.right { right: 0; width: 33%; }
.zone.center { left: 33%; width: 34%; }
.pill {
  position: absolute; bottom: 14px; left: 50%; transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.55); color: #fff; border-radius: var(--radius-pill);
  padding: 6px 14px; font-size: 13px; font-variant-numeric: tabular-nums; pointer-events: none;
}
.off { color: #ffc9b0; font-weight: 600; }
.bar {
  position: absolute; top: 12px; left: 50%; transform: translateX(-50%);
  display: flex; align-items: center; gap: 14px; padding: 10px 14px; flex-wrap: wrap;
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg);
  box-shadow: var(--shadow-2); z-index: 5;
}
.chk { display: flex; align-items: center; gap: 6px; font-size: var(--text-sm); }
.seg { display: inline-flex; background: var(--paper); border: 1px solid var(--border); border-radius: var(--radius-pill); padding: 3px; }
.seg button { border: none; background: none; color: var(--ink-2); font: inherit; font-size: 12px; padding: 4px 10px; border-radius: var(--radius-pill); cursor: pointer; }
.seg button.active { background: var(--accent-tint); color: var(--accent-strong); }
</style>
