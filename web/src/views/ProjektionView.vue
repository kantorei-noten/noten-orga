<script setup>
import * as pdfjsLib from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api } from '@/api'

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl

const route = useRoute()
const router = useRouter()
const setliste = ref(null)
const laden = ref(true)
const bauen = ref(false)
let prevTheme = 'light'

// Modus: was am Beamer erscheint. 'text' = Gemeinde-Ansage, 'noten' = Notenblatt, 'beides' = Titel-Folie + Noten.
const modus = ref(localStorage.getItem('proj-modus') || 'beides')
const eintraege = computed(() => setliste.value?.eintraege || [])

// Flache Folienliste: {kind:'text'|'page', entry, heading?, dateiId?, page?}
const slides = ref([])
const idx = ref(0)
const aktuell = computed(() => slides.value[idx.value] || null)

const viewport = ref(null)
const canvasEl = ref(null)

// --- PDF laden (offline-fest wie im Spielmodus) ---
const pdfCache = new Map()
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

// Liedtext in Folien aufteilen: Strophen (Leerzeile) bevorzugt, sonst nach Wortzahl chunken
function paginiereLyrics(text) {
  const stanzas = text.split(/\n\s*\n/).map((s) => s.trim()).filter(Boolean)
  const MAXZEILEN = 8
  const out = []
  for (const st of stanzas) {
    const zeilen = st.split(/\n/)
    if (zeilen.length <= MAXZEILEN) out.push(st)
    else for (let i = 0; i < zeilen.length; i += MAXZEILEN) out.push(zeilen.slice(i, i + MAXZEILEN).join('\n'))
  }
  // Extraktion liefert oft einen Fließtext ohne Umbrüche → nach Wortzahl aufteilen
  if (out.length === 1 && !/\n/.test(out[0]) && out[0].length > 320) {
    const w = out[0].split(/\s+/)
    const CH = 40
    const chunks = []
    for (let i = 0; i < w.length; i += CH) chunks.push(w.slice(i, i + CH).join(' '))
    return chunks
  }
  return out.length ? out : [text]
}

// --- Folien aus Einträgen + Modus bauen ---
async function baueSlides() {
  bauen.value = true
  const out = []
  const m = modus.value
  const wantText = m === 'text' || m === 'beides'
  const wantLyric = m === 'liedtext'
  const wantNoten = m === 'noten' || m === 'beides'
  for (const e of eintraege.value) {
    if (e.typ === 'abschnitt') {
      out.push({ kind: 'text', entry: e, heading: true })
      continue
    }
    if (wantText) out.push({ kind: 'text', entry: e })
    if (wantLyric) {
      const lt = (e.projektionstext || '').trim()
      if (lt) for (const chunk of paginiereLyrics(lt)) out.push({ kind: 'lyric', entry: e, text: chunk })
      else out.push({ kind: 'text', entry: e }) // Fallback: Titel-Folie
    }
    if (wantNoten && e.datei_id) {
      try {
        const pdf = await getPdf(e.datei_id)
        const von = e.seite_von && e.seite_von >= 1 ? e.seite_von : 1
        const bis = e.seite_bis && e.seite_bis >= von ? Math.min(e.seite_bis, pdf.numPages) : pdf.numPages
        for (let p = von; p <= bis; p++) out.push({ kind: 'page', entry: e, dateiId: e.datei_id, page: p })
      } catch {
        // Datei nicht ladbar → im Noten-Modus wenigstens den Titel zeigen, damit das Stück nicht verschwindet
        if (!wantText) out.push({ kind: 'text', entry: e })
      }
    } else if (wantNoten && !wantText) {
      // reiner Noten-Modus, aber Werk hat keine Datei → Titel zeigen statt Stück auszulassen
      out.push({ kind: 'text', entry: e })
    }
  }
  slides.value = out
  idx.value = 0
  bauen.value = false
  await nextTick()
  measure()
  if (aktuell.value?.kind === 'page') render()
}

function setModus(m) {
  if (modus.value === m) return
  modus.value = m
  localStorage.setItem('proj-modus', m)
  baueSlides()
}

// --- Noten-Rendering (serialisiert, Offscreen-Weißfläche wie im Spielmodus) ---
let rendering = false
let renderPending = false
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
  const item = aktuell.value
  if (!item || item.kind !== 'page' || !canvasEl.value || !viewport.value) return
  const pdf = await getPdf(item.dateiId)
  const page = await pdf.getPage(item.page)
  const base = page.getViewport({ scale: 1 })
  const availW = viewport.value.clientWidth
  const availH = viewport.value.clientHeight
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  // Ganze Seite in das Fenster einpassen (contain) — der Chor soll die komplette Seite sehen
  const cssScale = Math.min(availW / base.width, availH / base.height)
  const renderScale = Math.min(cssScale * dpr, 3000 / base.width)
  const vp = page.getViewport({ scale: renderScale })
  const off = document.createElement('canvas')
  off.width = Math.max(1, Math.floor(vp.width))
  off.height = Math.max(1, Math.floor(vp.height))
  const offctx = off.getContext('2d')
  offctx.fillStyle = '#ffffff'
  offctx.fillRect(0, 0, off.width, off.height)
  await page.render({ canvasContext: offctx, viewport: vp }).promise.catch(() => {})
  const c = canvasEl.value
  if (!c) return
  c.width = off.width
  c.height = off.height
  c.style.width = Math.floor(base.width * cssScale) + 'px'
  c.style.height = Math.floor(base.height * cssScale) + 'px'
  c.getContext('2d').drawImage(off, 0, 0)
  // nächste Seite vorladen
  const nx = slides.value[idx.value + 1]
  if (nx?.kind === 'page') getPdf(nx.dateiId).then((p) => p.getPage(nx.page)).catch(() => {})
}

// --- Navigation ---
function next() {
  if (idx.value < slides.value.length - 1) {
    idx.value++
  }
}
function prev() {
  if (idx.value > 0) {
    idx.value--
  }
}
watch(idx, async () => {
  if (aktuell.value?.kind === 'page') {
    await nextTick()
    render()
  }
})

function onKey(e) {
  if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') {
    e.preventDefault()
    next()
  } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
    e.preventDefault()
    prev()
  } else if (e.key === 'Escape') {
    raus()
  }
}

function titel(e) {
  return e?.werk_titel || e?.titel || ''
}

function measure() {
  /* nur zum Auslösen eines Reflows vor render() */
}
let resizeTimer = 0
function onResize() {
  clearTimeout(resizeTimer)
  resizeTimer = setTimeout(() => {
    if (aktuell.value?.kind === 'page') render()
  }, 140)
}

function raus() {
  router.push(
    setliste.value ? { name: 'setliste', params: { id: setliste.value.id } } : { name: 'setlisten' }
  )
}

onMounted(async () => {
  prevTheme = document.documentElement.dataset.theme || 'light'
  document.documentElement.dataset.theme = 'dark'
  window.addEventListener('keydown', onKey)
  window.addEventListener('resize', onResize)
  try {
    setliste.value = await api.get(`/setlisten/${route.params.setlisteId}`)
  } catch {
    /* leer */
  } finally {
    laden.value = false
  }
  await baueSlides()
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('resize', onResize)
  document.documentElement.dataset.theme = prevTheme
})
</script>

<template>
  <div class="proj">
    <div class="seg" @click.stop>
      <button :class="{ active: modus === 'text' }" @click="setModus('text')" title="Nur Titel (Ansage)">Titel</button>
      <button :class="{ active: modus === 'liedtext' }" @click="setModus('liedtext')" title="Liedtext für die Gemeinde">Liedtext</button>
      <button :class="{ active: modus === 'noten' }" @click="setModus('noten')" title="Notenblatt">Noten</button>
      <button :class="{ active: modus === 'beides' }" @click="setModus('beides')" title="Titel-Folie + Noten">Beides</button>
    </div>
    <button class="exit" @click="raus">✕</button>

    <div v-if="laden || bauen" class="slide"><div class="t">Lädt …</div></div>

    <template v-else-if="aktuell">
      <div class="zone l" @click="prev" />
      <div class="zone r" @click="next" />

      <!-- Text-Folie: Gemeinde-Ansage bzw. Zwischenüberschrift -->
      <div v-if="aktuell.kind === 'text'" class="slide">
        <div class="t" :class="{ heading: aktuell.heading }">{{ titel(aktuell.entry) }}</div>
        <div v-if="!aktuell.heading && aktuell.entry.komponist" class="sub">{{ aktuell.entry.komponist }}</div>
      </div>

      <!-- Liedtext-Folie -->
      <div v-else-if="aktuell.kind === 'lyric'" class="slide">
        <pre class="lyric">{{ aktuell.text }}</pre>
      </div>

      <!-- Noten-Folie -->
      <div v-else class="noten" ref="viewport">
        <canvas ref="canvasEl" class="page" />
      </div>

      <div class="ind">{{ idx + 1 }} / {{ slides.length }}</div>
    </template>

    <div v-else class="slide">
      <div class="t" style="font-size: 3vw">
        {{ modus === 'noten' ? 'Keine Noten in dieser Setliste' : 'Keine Einträge in dieser Setliste' }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.proj { position: fixed; inset: 0; background: #0b0d11; color: #f2f4f8; display: flex; align-items: center; justify-content: center; overflow: hidden; }
.slide { text-align: center; padding: 5vw; max-width: 92vw; }
.t { font-size: 6vw; font-weight: 700; line-height: 1.12; }
.t.heading { font-size: 4.5vw; color: #cfd6e2; letter-spacing: 0.02em; }
.sub { font-size: 3vw; color: #aab2c0; margin-top: 2vh; }
.lyric { font-family: inherit; white-space: pre-wrap; font-size: 3.4vw; font-weight: 600; line-height: 1.35; text-align: center; max-width: 88vw; margin: 0 auto; }
.noten { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; padding: 1vw; }
.page { display: block; background: #fff; box-shadow: 0 0 40px rgba(0, 0, 0, 0.6); }
.zone { position: absolute; top: 0; bottom: 0; width: 40%; cursor: pointer; z-index: 1; }
.zone.l { left: 0; }
.zone.r { right: 0; }
.ind { position: absolute; bottom: 16px; left: 50%; transform: translateX(-50%); color: #8892a2; font-size: 14px; font-variant-numeric: tabular-nums; z-index: 2; pointer-events: none; }
.exit { position: absolute; top: 14px; right: 16px; z-index: 3; background: rgba(255, 255, 255, 0.12); color: #fff; border: none; border-radius: 8px; width: 38px; height: 38px; font-size: 18px; cursor: pointer; }
.seg { position: absolute; top: 14px; left: 16px; z-index: 3; display: inline-flex; background: rgba(255, 255, 255, 0.1); border-radius: var(--radius-pill); padding: 3px; }
.seg button { border: none; background: none; color: #cfd6e2; font: inherit; font-size: 13px; padding: 5px 12px; border-radius: var(--radius-pill); cursor: pointer; }
.seg button.active { background: #fff; color: #16181d; font-weight: 600; }
</style>
