<script setup>
import { nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

import { api } from '@/api'
import { renderMusicXmlSeiten, SEITE_RATIO, SEITEN_OPTS, svgZuBild } from '@/lib/verovio'

// pdf.js nur bei Bedarf nachladen
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
let pdfjsLib = null
async function ensurePdfjs() {
  if (!pdfjsLib) {
    pdfjsLib = await import('pdfjs-dist')
    pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl
  }
  return pdfjsLib
}

const props = defineProps({
  ausgabeId: { type: String, required: true },
  dateiId: { type: String, default: '' },
  seiten: { type: Number, default: 1 },
  art: { type: String, default: 'scan_pdf' },
  // Seiten-Offset, damit mehrere Dateien EINER Ausgabe getrennte Notizen bekommen
  // (Annotationen sind per ausgabe+seite; jede Datei erhält einen eigenen Seitenbereich).
  seiteBasis: { type: Number, default: 0 }
})

const EBENEN = [
  { key: 'fingersatz', label: 'Fingersatz', color: '#2E6EB5' },
  { key: 'registrierung', label: 'Registrierung', color: '#2E9E5B' },
  { key: 'notiz', label: 'Notiz', color: '#C4463F' }
]
const farbe = (k) => EBENEN.find((e) => e.key === k)?.color || '#333'
const label = (k) => EBENEN.find((e) => e.key === k)?.label || ''

const aktiv = ref('notiz')
const modus = ref('text') // 'text' | 'zeichnen'
const schriftgroesse = ref(16)
const sichtbar = reactive({ fingersatz: true, registrierung: true, notiz: true })
const texts = reactive({ fingersatz: [], registrierung: [], notiz: [] })
// Striche imperativ auf Canvas → NICHT reaktiv (sonst langsam). Nur zum Speichern/Neuzeichnen.
let strokes = { fingersatz: [], registrierung: [], notiz: [] } // je: { punkte: [[x,y]…] } normalisiert 0..1000

const seite = ref(1)
const gesamtSeiten = ref(props.seiten || 1)
const stageEl = ref(null)
const bgCanvas = ref(null)
const drawCanvas = ref(null)
const stageAspect = ref('3 / 4')
const status = ref('')
const fokusText = ref(null)
let pdfDoc = null
let xmlSvgs = null // gerenderte MusicXML-Seiten (SVG-Strings)

// ---------- Zeichnen (imperativ, sofort) ----------
let zeichnend = false
let curStroke = null
let lastPx = null
function evToNorm(ev) {
  const r = drawCanvas.value.getBoundingClientRect()
  return [((ev.clientX - r.left) / r.width) * 1000, ((ev.clientY - r.top) / r.height) * 1000]
}
function normToPx(x, y) {
  const c = drawCanvas.value
  return [(x / 1000) * c.width, (y / 1000) * c.height]
}
function setStil(ctx, key) {
  ctx.strokeStyle = farbe(key)
  ctx.lineWidth = Math.max(1.5, (4 / 1000) * drawCanvas.value.width)
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
}
function stageDown(ev) {
  const [nx, ny] = evToNorm(ev)
  if (modus.value === 'text') {
    ev.preventDefault()
    const neu = { x: nx, y: ny, text: '', size: schriftgroesse.value }
    texts[aktiv.value].push(neu)
    fokusText.value = neu
    nextTick(() => {
      const l = stageEl.value?.querySelectorAll('.txt-' + aktiv.value)
      l?.[l.length - 1]?.focus()
    })
    return
  }
  ev.preventDefault()
  zeichnend = true
  curStroke = { punkte: [[nx, ny]] }
  strokes[aktiv.value].push(curStroke)
  const ctx = drawCanvas.value.getContext('2d')
  setStil(ctx, aktiv.value)
  lastPx = normToPx(nx, ny)
  ctx.beginPath()
  ctx.moveTo(lastPx[0], lastPx[1])
  ctx.lineTo(lastPx[0] + 0.1, lastPx[1] + 0.1)
  ctx.stroke()
}
function stageMove(ev) {
  if (!zeichnend) return
  const [nx, ny] = evToNorm(ev)
  curStroke.punkte.push([nx, ny])
  const ctx = drawCanvas.value.getContext('2d')
  const [px, py] = normToPx(nx, ny)
  setStil(ctx, aktiv.value)
  ctx.beginPath()
  ctx.moveTo(lastPx[0], lastPx[1])
  ctx.lineTo(px, py)
  ctx.stroke()
  lastPx = [px, py]
}
function stageUp() {
  zeichnend = false
  curStroke = null
  lastPx = null
}
function redrawAll() {
  const c = drawCanvas.value
  if (!c) return
  const ctx = c.getContext('2d')
  ctx.clearRect(0, 0, c.width, c.height)
  for (const e of EBENEN) {
    if (!sichtbar[e.key]) continue
    for (const s of strokes[e.key]) {
      if (!s.punkte?.length) continue
      setStil(ctx, e.key)
      ctx.beginPath()
      const [x0, y0] = normToPx(s.punkte[0][0], s.punkte[0][1])
      ctx.moveTo(x0, y0)
      for (let i = 1; i < s.punkte.length; i++) {
        const [x, y] = normToPx(s.punkte[i][0], s.punkte[i][1])
        ctx.lineTo(x, y)
      }
      ctx.stroke()
    }
  }
}
watch(sichtbar, redrawAll, { deep: true })

// ---------- Text: ziehen, löschen, Größe ----------
let dragText = null
function dragStart(ev, t) {
  ev.preventDefault()
  ev.stopPropagation()
  dragText = t
  fokusText.value = t
  window.addEventListener('pointermove', dragMove)
  window.addEventListener('pointerup', dragEnd)
}
function dragMove(ev) {
  if (!dragText || !stageEl.value) return
  const r = stageEl.value.getBoundingClientRect()
  dragText.x = Math.min(1000, Math.max(0, ((ev.clientX - r.left) / r.width) * 1000))
  dragText.y = Math.min(1000, Math.max(0, ((ev.clientY - r.top) / r.height) * 1000))
}
function dragEnd() {
  dragText = null
  window.removeEventListener('pointermove', dragMove)
  window.removeEventListener('pointerup', dragEnd)
}
function textBlur(key, i) {
  if (!(texts[key][i]?.text || '').trim()) texts[key].splice(i, 1)
}
function textLoeschen(key, i) {
  texts[key].splice(i, 1)
  fokusText.value = null
}
function setGroesse(v) {
  schriftgroesse.value = v
  if (fokusText.value) fokusText.value.size = v
}

// ---------- Noten-Hintergrund ----------
async function ladePdf() {
  if (!props.dateiId) {
    await nextTick()
    if (drawCanvas.value && bgCanvas.value) {
      bgCanvas.value.width = drawCanvas.value.width = 1000
      bgCanvas.value.height = drawCanvas.value.height = 1333
    }
    redrawAll()
    return
  }
  if (props.art === 'musicxml') {
    try {
      xmlSvgs = await renderMusicXmlSeiten(props.dateiId)
      gesamtSeiten.value = xmlSvgs.length
      await renderSeiteXml()
    } catch {
      redrawAll()
    }
    return
  }
  try {
    const res = await fetch(`/api/dateien/${props.dateiId}/download`, { credentials: 'include' })
    const buf = await res.arrayBuffer()
    const lib = await ensurePdfjs()
    pdfDoc = await lib.getDocument({ data: buf }).promise
    gesamtSeiten.value = pdfDoc.numPages
    await renderSeite()
  } catch {
    redrawAll()
  }
}
async function renderSeiteXml() {
  if (!xmlSvgs || !bgCanvas.value) return
  stageAspect.value = `${SEITEN_OPTS.pageWidth} / ${SEITEN_OPTS.pageHeight}`
  await nextTick()
  const W = 1400
  const H = Math.round(W / SEITE_RATIO)
  const bg = bgCanvas.value
  const dc = drawCanvas.value
  bg.width = dc.width = W
  bg.height = dc.height = H
  const bctx = bg.getContext('2d')
  bctx.fillStyle = '#ffffff'
  bctx.fillRect(0, 0, W, H)
  try {
    const { img, url } = await svgZuBild(xmlSvgs[seite.value - 1])
    bctx.drawImage(img, 0, 0, W, H)
    URL.revokeObjectURL(url)
  } catch {
    /* weißer Hintergrund bleibt */
  }
  redrawAll()
}

async function renderSeite() {
  if (props.art === 'musicxml') return renderSeiteXml()
  if (!pdfDoc || !bgCanvas.value) return
  const page = await pdfDoc.getPage(seite.value)
  const base = page.getViewport({ scale: 1 })
  stageAspect.value = `${base.width} / ${base.height}`
  await nextTick()
  const vp = page.getViewport({ scale: 1400 / base.width })
  const bg = bgCanvas.value
  const dc = drawCanvas.value
  bg.width = dc.width = Math.floor(vp.width)
  bg.height = dc.height = Math.floor(vp.height)
  const bctx = bg.getContext('2d')
  bctx.fillStyle = '#ffffff'
  bctx.fillRect(0, 0, bg.width, bg.height)
  await page.render({ canvasContext: bctx, viewport: vp }).promise.catch(() => {})
  redrawAll()
}

// ---------- Laden / Speichern (pro Seite) ----------
async function load() {
  const rows = await api.get(`/ausgaben/${props.ausgabeId}/annotationen?seite=${props.seiteBasis + seite.value}`)
  strokes = { fingersatz: [], registrierung: [], notiz: [] }
  for (const e of EBENEN) texts[e.key] = []
  for (const row of rows) {
    if (strokes[row.ebene] === undefined) continue
    const d = row.daten || {}
    // neues Format {strokes,texts}; altes {paths:[[[x,y]…]…]} migrieren
    strokes[row.ebene] = d.strokes || (d.paths || []).map((p) => ({ punkte: p }))
    texts[row.ebene] = (d.texts || []).map((t) => ({ ...t, size: t.size || 16 }))
  }
  redrawAll()
}
async function speichern() {
  status.value = 'Speichern …'
  for (const e of EBENEN) {
    await api.put(`/ausgaben/${props.ausgabeId}/annotationen`, {
      ebene: e.key,
      seite: props.seiteBasis + seite.value,
      daten: { strokes: strokes[e.key], texts: texts[e.key] }
    })
  }
  status.value = 'Gespeichert'
  setTimeout(() => (status.value = ''), 1500)
}
function ebeneLeeren() {
  strokes[aktiv.value] = []
  texts[aktiv.value] = []
  redrawAll()
}
function rueckgaengig() {
  if (strokes[aktiv.value].length) {
    strokes[aktiv.value].pop()
    redrawAll()
  }
}
async function blaettern(delta) {
  const ziel = Math.min(gesamtSeiten.value, Math.max(1, seite.value + delta))
  if (ziel === seite.value) return
  await speichern()
  seite.value = ziel
  await load()
  await renderSeite()
}

onMounted(async () => {
  await load()
  await ladePdf()
})
onBeforeUnmount(() => {
  window.removeEventListener('pointermove', dragMove)
  window.removeEventListener('pointerup', dragEnd)
})
</script>

<template>
  <div class="ann card">
    <div class="toolbar" style="flex-wrap: wrap; margin: 0 0 8px; gap: 8px; align-items: center">
      <div class="seg">
        <button :class="{ active: modus === 'text' }" @click="modus = 'text'">⌨︎ Text</button>
        <button :class="{ active: modus === 'zeichnen' }" @click="modus = 'zeichnen'">✎ Zeichnen</button>
      </div>
      <span class="trenner" />
      <button
        v-for="e in EBENEN"
        :key="e.key"
        class="chip"
        :class="{ active: aktiv === e.key }"
        @click="aktiv = e.key"
      >
        <span class="dot" :style="{ background: e.color }" />{{ e.label }}
      </button>
      <label class="size">Größe
        <select :value="fokusText ? fokusText.size : schriftgroesse" @change="setGroesse(+$event.target.value)">
          <option :value="11">S</option>
          <option :value="16">M</option>
          <option :value="22">L</option>
          <option :value="30">XL</option>
        </select>
      </label>
      <span style="flex: 1" />
      <label v-for="e in EBENEN" :key="'v' + e.key" class="vis">
        <input type="checkbox" v-model="sichtbar[e.key]" /> {{ e.label }}
      </label>
    </div>

    <div ref="stageEl" class="stage" :style="{ aspectRatio: stageAspect }">
      <canvas ref="bgCanvas" class="bg" />
      <canvas
        ref="drawCanvas"
        class="draw"
        :class="{ textmodus: modus === 'text' }"
        @pointerdown="stageDown"
        @pointermove="stageMove"
        @pointerup="stageUp"
        @pointerleave="stageUp"
      />
      <template v-for="e in EBENEN" :key="'t' + e.key">
        <div
          v-for="(t, i) in sichtbar[e.key] ? texts[e.key] : []"
          :key="e.key + 't' + i"
          class="txtwrap"
          :style="{ left: t.x / 10 + '%', top: t.y / 10 + '%', pointerEvents: modus === 'text' ? 'auto' : 'none' }"
        >
          <span v-if="modus === 'text'" class="grip" title="Ziehen zum Verschieben" @pointerdown="dragStart($event, t)">⠿</span>
          <input
            :class="['txt', 'txt-' + e.key]"
            v-model="t.text"
            :readonly="modus !== 'text'"
            :size="Math.max(2, (t.text || '').length + 1)"
            :style="{ fontSize: t.size + 'px', color: e.color, borderColor: e.color }"
            placeholder="…"
            @focus="fokusText = t"
            @pointerdown.stop
            @blur="textBlur(e.key, i)"
          />
          <button v-if="modus === 'text'" class="txtdel" title="Löschen" @click="textLoeschen(e.key, i)">×</button>
        </div>
      </template>
    </div>

    <div class="toolbar" style="margin: 8px 0 0; gap: 8px; align-items: center">
      <button class="btn sm primary" @click="speichern">Speichern</button>
      <button class="btn sm ghost" @click="rueckgaengig">Rückgängig</button>
      <button class="btn sm ghost" @click="ebeneLeeren">Ebene leeren</button>
      <span style="flex: 1" />
      <template v-if="gesamtSeiten > 1">
        <button class="btn sm secondary" :disabled="seite <= 1" @click="blaettern(-1)">‹</button>
        <span class="muted">Seite {{ seite }} / {{ gesamtSeiten }}</span>
        <button class="btn sm secondary" :disabled="seite >= gesamtSeiten" @click="blaettern(1)">›</button>
      </template>
      <span class="muted">{{ status }}</span>
    </div>
    <p class="muted hint">
      <template v-if="modus === 'text'">Auf die Noten klicken → Text tippen · <b>⠿</b> ziehen zum Verschieben · Größe oben einstellbar</template>
      <template v-else>Mit Maus/Finger auf die Noten zeichnen</template>
      · Ebene: <b>{{ label(aktiv) }}</b>
    </p>
  </div>
</template>

<style scoped>
.stage {
  position: relative;
  width: 100%;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.bg,
.draw { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }
.draw { touch-action: none; cursor: crosshair; }
.draw.textmodus { cursor: text; }
.txtwrap { position: absolute; display: flex; align-items: flex-start; gap: 2px; transform: translate(-1px, -1px); }
.grip { cursor: move; user-select: none; font-size: 13px; line-height: 1.4; padding: 0 2px; color: #555; background: rgba(255, 255, 255, 0.85); border-radius: 4px; }
.txt {
  font-weight: 600;
  background: rgba(255, 255, 255, 0.9);
  border: 1.5px solid;
  border-radius: 6px;
  padding: 1px 5px;
  min-width: 34px;
  line-height: 1.25;
}
.txt[readonly] { background: rgba(255, 255, 255, 0.55); border-color: transparent !important; cursor: default; padding: 1px 3px; }
.txtdel { border: none; background: var(--ink); color: #fff; width: 16px; height: 16px; line-height: 14px; border-radius: 50%; font-size: 12px; cursor: pointer; padding: 0; }
.size { font-size: 12px; color: var(--ink-2); display: inline-flex; align-items: center; gap: 4px; }
.size select { font: inherit; padding: 2px 4px; }
.seg { display: inline-flex; background: var(--paper); border: 1px solid var(--border); border-radius: var(--radius-pill); padding: 3px; }
.seg button { border: none; background: none; color: var(--ink-2); font: inherit; font-size: 12px; padding: 4px 10px; border-radius: var(--radius-pill); cursor: pointer; }
.seg button.active { background: var(--accent-tint); color: var(--accent-strong); }
.trenner { width: 1px; height: 20px; background: var(--border); }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; vertical-align: 1px; }
.vis { font-size: 12px; color: var(--ink-2); margin-left: 8px; }
.chip { display: inline-flex; align-items: center; height: 30px; padding: 0 11px; border-radius: var(--radius-pill); border: 1px solid var(--border-strong); background: var(--paper); cursor: pointer; font-size: var(--text-sm); }
.chip.active { border-color: var(--accent); background: var(--accent-tint); }
.hint { font-size: 12px; margin: 8px 2px 0; }
</style>
