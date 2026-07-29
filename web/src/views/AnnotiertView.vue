<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api } from '@/api'
import { zeichneAnnotationen } from '@/lib/annotationsDraw'
import { renderMusicXmlSeiten, SEITE_RATIO, svgZuBild } from '@/lib/verovio'

// pdf.js lazy laden
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
let pdfjsLib = null
async function ensurePdfjs() {
  if (!pdfjsLib) {
    pdfjsLib = await import('pdfjs-dist')
    pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl
  }
  return pdfjsLib
}

const route = useRoute()
const router = useRouter()
const titel = ref(route.query.titel || 'Notenblatt mit Notizen')
const laden = ref(true)
const fehler = ref('')
const container = ref(null)
let canvases = []

const istXml = route.query.art === 'musicxml'
const spielZiel = istXml
  ? { name: 'noten', params: { dateiId: route.query.datei } }
  : {
      name: 'spielen',
      query: {
        dateien: route.query.datei,
        titel: titel.value,
        werk: route.query.werk,
        ausgabe: route.query.ausgabe
      }
    }

function esc(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
function dateiname(ext) {
  const b = String(titel.value || 'notenblatt').replace(/[^\wäöüÄÖÜß\- ]+/g, '').trim().replace(/\s+/g, '_')
  return (b || 'notenblatt') + '_Notizen' + ext
}

async function baue() {
  const dateiId = route.query.datei
  const ausgabeId = route.query.ausgabe
  if (!dateiId) {
    fehler.value = 'Keine Datei angegeben.'
    laden.value = false
    return
  }
  if (istXml) {
    try {
      const svgs = await renderMusicXmlSeiten(dateiId)
      const W = 1400
      const H = Math.round(W / SEITE_RATIO)
      for (let p = 1; p <= svgs.length; p++) {
        const c = document.createElement('canvas')
        c.width = W
        c.height = H
        c.style.cssText = 'width:min(100%,900px);height:auto;box-shadow:var(--shadow-2);background:#fff;border-radius:4px'
        const ctx = c.getContext('2d')
        ctx.fillStyle = '#ffffff'
        ctx.fillRect(0, 0, W, H)
        try {
          const { img, url } = await svgZuBild(svgs[p - 1])
          ctx.drawImage(img, 0, 0, W, H)
          URL.revokeObjectURL(url)
        } catch {
          /* weiße Seite */
        }
        if (ausgabeId) {
          try {
            const rows = await api.get(`/ausgaben/${ausgabeId}/annotationen?seite=${(Number(route.query.basis) || 0) + p}`)
            zeichneAnnotationen(ctx, W, H, rows)
          } catch {
            /* ohne Overlay weiter */
          }
        }
        canvases.push(c)
        container.value?.appendChild(c)
      }
      if (!canvases.length) fehler.value = 'Keine Seiten gefunden.'
    } catch {
      fehler.value = 'Das Notenblatt konnte nicht geladen werden.'
    } finally {
      laden.value = false
    }
    return
  }
  try {
    const res = await fetch(`/api/dateien/${dateiId}/download`, { credentials: 'include' })
    const buf = await res.arrayBuffer()
    const lib = await ensurePdfjs()
    const pdf = await lib.getDocument({ data: buf }).promise
    for (let p = 1; p <= pdf.numPages; p++) {
      const page = await pdf.getPage(p)
      const base = page.getViewport({ scale: 1 })
      const vp = page.getViewport({ scale: 1400 / base.width })
      const c = document.createElement('canvas')
      c.width = Math.floor(vp.width)
      c.height = Math.floor(vp.height)
      c.style.cssText = 'width:min(100%,900px);height:auto;box-shadow:var(--shadow-2);background:#fff;border-radius:4px'
      const ctx = c.getContext('2d')
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, c.width, c.height)
      await page.render({ canvasContext: ctx, viewport: vp }).promise.catch(() => {})
      if (ausgabeId) {
        try {
          const rows = await api.get(`/ausgaben/${ausgabeId}/annotationen?seite=${(Number(route.query.basis) || 0) + p}`)
          zeichneAnnotationen(ctx, c.width, c.height, rows)
        } catch {
          /* ohne Overlay weiter */
        }
      }
      canvases.push(c)
      container.value?.appendChild(c)
    }
    if (!canvases.length) fehler.value = 'Keine Seiten gefunden.'
  } catch {
    fehler.value = 'Das Notenblatt konnte nicht geladen werden.'
  } finally {
    laden.value = false
  }
}

function raus() {
  if (route.query.werk) router.push({ name: 'werk', params: { id: route.query.werk } })
  else router.push({ name: 'katalog' })
}

function drucken() {
  if (!canvases.length) return
  const imgs = canvases.map((c) => `<img src="${c.toDataURL('image/png')}" />`).join('')
  const html =
    '<!doctype html><html lang="de"><head><meta charset="utf-8"><title>' +
    esc(titel.value) +
    '</title><style>*{margin:0}img{display:block;width:100%;page-break-after:always}@page{margin:10mm}</style></head><body>' +
    imgs +
    '</body></html>'
  const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }))
  const f = document.createElement('iframe')
  f.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0'
  let fertig = false
  const cleanup = () => {
    if (fertig) return
    fertig = true
    setTimeout(() => {
      f.remove()
      URL.revokeObjectURL(url)
    }, 500)
  }
  f.onload = () => {
    try {
      f.contentWindow.addEventListener('afterprint', cleanup)
      f.contentWindow.focus()
      f.contentWindow.print()
    } catch {
      cleanup()
    }
    setTimeout(cleanup, 60000)
  }
  f.src = url
  document.body.appendChild(f)
}

// Alle Seiten in ein hohes Canvas → ein Bild zum Speichern/Senden
function kombiniert() {
  const w = Math.max(...canvases.map((c) => c.width))
  const h = canvases.reduce((s, c) => s + c.height + 10, 0)
  const big = document.createElement('canvas')
  big.width = w
  big.height = h
  const ctx = big.getContext('2d')
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, w, h)
  let y = 0
  for (const c of canvases) {
    ctx.drawImage(c, 0, y)
    y += c.height + 10
  }
  return big
}
function speichern() {
  if (!canvases.length) return
  kombiniert().toBlob((blob) => {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = dateiname('.png')
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }, 'image/png')
}
async function senden() {
  if (!canvases.length) return
  kombiniert().toBlob(async (blob) => {
    const file = new File([blob], dateiname('.png'), { type: 'image/png' })
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      try {
        await navigator.share({ files: [file], title: titel.value })
      } catch {
        /* abgebrochen */
      }
      return
    }
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = dateiname('.png')
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    alert('Direktes Teilen wird hier nicht unterstützt — das Bild wurde heruntergeladen und kann angehängt werden.')
  }, 'image/png')
}

onMounted(baue)
</script>

<template>
  <div class="annv">
    <div class="topbar">
      <button class="btn sm secondary" @click="raus">← Zurück</button>
      <b class="titel">{{ titel }}</b>
      <span style="flex: 1" />
      <RouterLink class="btn sm secondary" :to="spielZiel">
        {{ istXml ? 'Spielansicht ▸' : 'Spielmodus ▸' }}
      </RouterLink>
      <button class="btn sm secondary" :disabled="laden" @click="drucken">Drucken</button>
      <button class="btn sm ghost" :disabled="laden" @click="speichern">Als Bild speichern</button>
      <button class="btn sm ghost" :disabled="laden" @click="senden">Senden</button>
    </div>
    <p v-if="laden" class="hint muted">Notenblatt mit Notizen wird zusammengesetzt …</p>
    <p v-else-if="fehler" class="hint muted">{{ fehler }}</p>
    <div ref="container" class="pages" />
  </div>
</template>

<style scoped>
.annv { position: fixed; inset: 0; display: flex; flex-direction: column; background: var(--paper); }
.topbar { display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-bottom: 1px solid var(--border); background: var(--surface); }
.topbar .titel { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hint { padding: 20px; }
.pages { flex: 1; overflow: auto; padding: 16px; display: flex; flex-direction: column; align-items: center; gap: 16px; }
</style>
