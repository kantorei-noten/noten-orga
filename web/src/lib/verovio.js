import createVerovioModule from 'verovio/wasm'
import { VerovioToolkit } from 'verovio/esm'

// Das Verovio-wasm-Modul ist teuer zu laden — nur einmal pro App-Sitzung.
// Jeder Aufruf liefert ein frisches Toolkit (billig) auf demselben Modul.
let modulPromise = null

export async function neuesToolkit() {
  if (!modulPromise) modulPromise = createVerovioModule()
  const modul = await modulPromise
  return new VerovioToolkit(modul)
}

// Stabile A4-Seitenoptionen. MUSS zwischen Notizen-Editor (AnnotationLayer) und
// Notizen-Ansicht (AnnotiertView) identisch sein, damit die Seitenzahlen — und
// damit die pro Seite gespeicherten Annotationen — übereinstimmen.
export const SEITEN_OPTS = {
  scale: 40,
  adjustPageHeight: false,
  pageWidth: 2100,
  pageHeight: 2970,
  breaks: 'auto',
  header: 'none',
  footer: 'none',
  pageMarginTop: 100,
  pageMarginBottom: 100,
  pageMarginLeft: 100,
  pageMarginRight: 100
}
export const SEITE_RATIO = SEITEN_OPTS.pageWidth / SEITEN_OPTS.pageHeight // ~0.707 (A4 hoch)

export async function ladeMusicXml(dateiId) {
  const res = await fetch(`/api/dateien/${dateiId}/musicxml`, { credentials: 'include' })
  if (!res.ok) throw new Error('MusicXML nicht verfügbar')
  return res.text()
}

// Rendert alle Seiten einer MusicXML-Datei als SVG-Strings (feste A4-Seiten).
export async function renderMusicXmlSeiten(dateiId, { transpose } = {}) {
  const xml = await ladeMusicXml(dateiId)
  const tk = await neuesToolkit()
  const opts = { ...SEITEN_OPTS }
  if (transpose) opts.transpose = transpose
  tk.setOptions(opts)
  tk.loadData(xml)
  const n = tk.getPageCount() || 1
  const svgs = []
  for (let p = 1; p <= n; p++) svgs.push(tk.renderToSVG(p))
  return svgs
}

// SVG-String -> geladenes <img> (zum Rastern auf ein Canvas). URL nach Gebrauch freigeben.
export function svgZuBild(svg) {
  // Für die Rasterung als Bild wird das SVG als eigenständiges XML geparst →
  // xmlns ist Pflicht (beim v-html-Einbetten nicht nötig, hier schon).
  if (!/\sxmlns=/.test(svg.slice(0, 300))) {
    svg = svg.replace(
      /<svg\b/,
      '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'
    )
  }
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }))
    const img = new Image()
    img.onload = () => resolve({ img, url })
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('SVG-Rasterung fehlgeschlagen'))
    }
    img.src = url
  })
}

// Druckt SVG-Seiten über ein verstecktes iframe (kein Popup-Blocker).
export function druckeSvgSeiten(svgs, titel = 'Noten') {
  if (!svgs?.length) return
  const esc = (s) => (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const html =
    '<!doctype html><html lang="de"><head><meta charset="utf-8"><title>' +
    esc(titel) +
    '</title><style>*{margin:0}@page{margin:8mm}.pg{page-break-after:always}' +
    'svg{display:block;width:100%;height:auto}</style></head><body>' +
    svgs.map((s) => `<div class="pg">${s}</div>`).join('') +
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
