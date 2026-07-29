// ChordPro exportieren: drucken (formatiert), als Datei speichern, versenden.
import { akkordeImText, parseDefines, parseZeile, songTranspose, transponiere, transponiereAkkord } from './chordpro'
import { griff } from './chordDB'

function esc(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

const START = {
  start_of_chorus: 'Refrain', soc: 'Refrain',
  start_of_verse: 'Strophe', sov: 'Strophe',
  start_of_bridge: 'Bridge', sob: 'Bridge',
  start_of_tab: 'Tabulatur', sot: 'Tabulatur',
  start_of_grid: 'Grid', sog: 'Grid',
  start_of_abc: 'ABC', start_of_ly: 'LilyPond', start_of_svg: 'SVG', start_of_textblock: ''
}
const ENDSET = new Set([
  'end_of_chorus', 'eoc', 'end_of_verse', 'eov', 'end_of_bridge', 'eob', 'end_of_tab', 'eot',
  'end_of_grid', 'eog', 'end_of_abc', 'end_of_ly', 'end_of_svg', 'end_of_textblock'
])
const META = {
  key: 'Tonart', capo: 'Kapodaster', tempo: 'Tempo', time: 'Taktart', duration: 'Dauer',
  artist: 'Interpret', composer: 'Komponist', lyricist: 'Text', copyright: '©', album: 'Album', year: 'Jahr', tag: 'Schlagwort'
}
const IGNORE = new Set([
  'new_song', 'ns', 'sorttitle', 'sortartist', 'image', 'pagetype', 'titles', 'grid', 'g', 'no_grid', 'ng',
  'columns', 'col', 'diagrams', 'define', 'chord', 'transpose',
  'textfont', 'tf', 'textsize', 'ts', 'textcolour', 'chordfont', 'cf', 'chordsize', 'cs', 'chordcolour',
  'chorusfont', 'chorussize', 'choruscolour', 'tabfont', 'tabsize', 'tabcolour', 'gridfont', 'gridsize', 'gridcolour',
  'titlefont', 'titlesize', 'titlecolour', 'footerfont', 'footersize', 'footercolour',
  'labelfont', 'labelsize', 'labelcolour', 'tocfont', 'tocsize', 'toccolour'
])

function zeileHtml(z, n) {
  if (z.typ === 'leer') return '<div class="leer"></div>'
  if (z.typ === 'ignoriert') return ''
  if (z.typ === 'direktive') {
    const name = z.name
    if (name === 'title' || name === 't') return '<h1>' + esc(z.wert) + '</h1>'
    if (name === 'subtitle' || name === 'st') return '<h2>' + esc(z.wert) + '</h2>'
    if (START[name] !== undefined) return '<p class="abschnitt">' + esc(z.wert || START[name]) + '</p>'
    if (ENDSET.has(name)) return ''
    if (name === 'chorus') return '<p class="abschnitt">↻ ' + esc(z.wert || 'Refrain') + '</p>'
    if (name === 'new_page' || name === 'np' || name === 'new_physical_page' || name === 'npp')
      return '<div style="break-after:page"></div>'
    if (name === 'column_break' || name === 'colb') return '<div style="break-after:column"></div>'
    if (META[name]) {
      const v = name === 'key' ? transponiereAkkord(z.wert, n) : z.wert
      const suffix = name === 'tempo' && /\d/.test(z.wert) ? ' BPM' : ''
      return '<p class="meta"><b>' + META[name] + ':</b> ' + esc(v) + suffix + '</p>'
    }
    if (name === 'meta') {
      const w = z.wert || ''
      const i = w.indexOf(' ')
      const k = i < 0 ? w : w.slice(0, i)
      const v = i < 0 ? '' : w.slice(i + 1)
      return '<p class="meta"><b>' + esc(k) + ':</b> ' + esc(v) + '</p>'
    }
    if (name === 'comment_box' || name === 'cb') return '<p class="cbox">' + esc(z.wert) + '</p>'
    if (name === 'highlight') return '<p class="hl">' + esc(z.wert) + '</p>'
    if (name === 'comment_italic' || name === 'ci') return '<p class="komm" style="font-style:italic">' + esc(z.wert) + '</p>'
    if (name === 'comment' || name === 'c') return '<p class="komm">' + esc(z.wert) + '</p>'
    return '' // Ausgabe-/Font-/Layout-/unbekannte Direktiven werden nicht gedruckt
  }
  let cols = ''
  for (const col of z.cols) {
    if (col.marke) {
      cols += '<span class="mk">' + esc(col.marke) + '</span>'
      continue
    }
    const oben = col.akkord || col.annotation || ''
    const cls = !col.akkord && col.annotation ? 'ch ann' : 'ch'
    cols += '<span class="col"><span class="' + cls + '">' + esc(oben) + '</span><span class="ly">' + esc(col.text || '') + '</span></span>'
  }
  return '<div class="line">' + cols + '</div>'
}

export function titelAus(text) {
  const m = (text || '').match(/\{\s*(?:title|t)\s*:\s*([^}]*)\}/i)
  return m ? m[1].trim() : ''
}

// --- Blöcke (farbige Hinterlegung) ---
const BLOCK = {
  start_of_chorus: 'chorus', soc: 'chorus',
  start_of_verse: 'verse', sov: 'verse',
  start_of_bridge: 'bridge', sob: 'bridge',
  start_of_tab: 'tab', sot: 'tab',
  start_of_grid: 'grid', sog: 'grid',
  start_of_abc: 'mono', start_of_ly: 'mono', start_of_svg: 'mono',
  start_of_textblock: 'plain'
}
const BLOCK_LBL = { chorus: 'Refrain', verse: 'Strophe', bridge: 'Bridge', tab: 'Tabulatur', grid: 'Grid' }

function baueKoerper(parsed, n) {
  let html = ''
  let offen = false
  const zu = () => {
    if (offen) {
      html += '</div>'
      offen = false
    }
  }
  for (const z of parsed) {
    if (z.typ === 'direktive' && BLOCK[z.name] !== undefined) {
      zu()
      const typ = BLOCK[z.name]
      const label = z.wert || BLOCK_LBL[typ] || ''
      html += `<div class="blk blk-${typ}">` + (label ? `<div class="blk-l">${esc(label)}</div>` : '')
      offen = true
      continue
    }
    if (z.typ === 'direktive' && ENDSET.has(z.name)) {
      zu()
      continue
    }
    html += zeileHtml(z, n)
  }
  zu()
  return html
}

// --- Akkord-Griffbilder als SVG ---
function diagrammSvg(name, frets, base) {
  const ST = 6
  const FR = 5
  const W = 48
  const padL = 8
  const padR = 8
  const padT = 15
  const areaH = 46
  const H = padT + areaH + 15
  const gapX = (W - padL - padR) / (ST - 1)
  const gapY = areaH / FR
  const xOf = (i) => padL + i * gapX
  const yOf = (f) => padT + f * gapY
  let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">`
  for (let f = 0; f <= FR; f++) {
    const y = yOf(f)
    const sw = f === 0 && base <= 1 ? 2.4 : 0.7
    s += `<line x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}" stroke="#111" stroke-width="${sw}"/>`
  }
  for (let i = 0; i < ST; i++) {
    const x = xOf(i)
    s += `<line x1="${x}" y1="${padT}" x2="${x}" y2="${padT + areaH}" stroke="#111" stroke-width="0.7"/>`
  }
  frets.forEach((v, i) => {
    const x = xOf(i)
    if (v === 0) s += `<text x="${x}" y="${padT - 4}" text-anchor="middle" font-size="6" fill="#555">o</text>`
    else if (v < 0) s += `<text x="${x}" y="${padT - 4}" text-anchor="middle" font-size="6" fill="#555">×</text>`
  })
  frets.forEach((v, i) => {
    if (v > 0) {
      const idx = v - (base - 1)
      if (idx >= 1 && idx <= FR) s += `<circle cx="${xOf(i)}" cy="${yOf(idx) - gapY / 2}" r="2.5" fill="#1a4f8a"/>`
    }
  })
  if (base > 1) s += `<text x="${padL - 3}" y="${padT + gapY - 1}" text-anchor="end" font-size="5" fill="#555">${base}fr</text>`
  s += `<text x="${W / 2}" y="${H - 4}" text-anchor="middle" font-size="8" font-weight="700" fill="#111">${esc(name)}</text></svg>`
  return s
}

function griffbilderHtml(text, eff) {
  const t = text || ''
  if (/\{\s*(no_grid|ng)\s*\}/i.test(t)) return ''
  const d = t.match(/\{\s*diagrams\s*:\s*([^}]*)\}/i)
  if (d && /^(none|off|no)/i.test((d[1] || '').trim())) return ''
  const defs = parseDefines(t)
  const namen = akkordeImText(transponiere(t, eff))
  const out = []
  const seen = new Set()
  const add = (nm, g) => {
    if (g) out.push(diagrammSvg(nm, g.frets, g.base))
  }
  for (const nm of namen) {
    if (seen.has(nm)) continue
    seen.add(nm)
    add(nm, defs[nm] || griff(nm))
  }
  for (const k in defs) {
    if (!seen.has(k)) {
      seen.add(k)
      add(k, defs[k])
    }
  }
  if (!out.length) return ''
  return `<div class="griffe"><div class="griffe-t">Griffbilder</div><div class="griffe-l">${out.join('')}</div></div>`
}

export function chordproDoc(text, halbtoene, titel) {
  const eff = (halbtoene || 0) + songTranspose(text || '')
  const n = (((eff % 12) + 12) % 12)
  const parsed = transponiere(text || '', eff).split('\n').map(parseZeile)
  let strophe = 0
  for (const z of parsed) {
    if (z.typ === 'direktive' && (z.name === 'start_of_verse' || z.name === 'sov')) {
      strophe += 1
      if (!z.wert) z.wert = 'Strophe ' + strophe
    }
  }
  const body = baueKoerper(parsed, n)
  const colM = (text || '').match(/\{\s*col(?:umns)?\s*:\s*(\d+)\s*\}/i)
  const spalten = colM ? Math.max(1, Math.min(3, parseInt(colM[1], 10))) : 1
  const bodyWrap = spalten > 1 ? `<div style="column-count:${spalten};column-gap:14mm">${body}</div>` : body
  const griffHtml = griffbilderHtml(text, eff)
  const t = esc(titel || titelAus(text) || 'Noten')
  return `<!doctype html><html lang="de"><head><meta charset="utf-8"><title>${t}</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: Georgia, 'Times New Roman', serif; color: #111; margin: 24px; font-size: 15px; line-height: 1.35; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  h1 { font-size: 22px; margin: 0 0 2px; }
  h2 { font-size: 16px; font-weight: normal; color: #555; margin: 0 0 10px; }
  .komm { color: #555; font-style: italic; margin: 6px 0; }
  .abschnitt { font-weight: 700; color: #1a4f8a; margin: 8px 0 2px; font-size: 0.82em; text-transform: uppercase; letter-spacing: 0.04em; }
  .meta { color: #555; margin: 1px 0; font-size: 0.92em; }
  .meta b { color: #111; }
  .cbox { border: 1px solid #999; border-radius: 6px; padding: 3px 9px; display: inline-block; margin: 4px 0; }
  .hl { background: #eef3fb; color: #1a4f8a; font-weight: 700; border-radius: 6px; padding: 3px 9px; display: inline-block; margin: 4px 0; }
  .ch.ann { color: #666; font-weight: 400; font-style: italic; }
  .leer { height: 12px; }
  .line { display: flex; flex-wrap: wrap; align-items: flex-end; margin: 2px 0; }
  .col { display: inline-flex; flex-direction: column; justify-content: flex-end; }
  .ch { color: #1a4f8a; font-weight: 700; font-size: 0.8em; height: 1.35em; line-height: 1.35em; white-space: pre; }
  .ly { white-space: pre; }
  .mk { align-self: center; margin: 0 6px; padding: 1px 8px; border: 1px solid #1a4f8a; border-radius: 999px; color: #1a4f8a; font-size: 0.8em; font-weight: 700; }
  .blk { margin: 8px 0; padding: 6px 10px; border-left: 3px solid #1a4f8a; border-radius: 0 6px 6px 0; break-inside: avoid; }
  .blk-chorus { background: #eef3fb; }
  .blk-verse { border-left-color: #bbbbbb; background: transparent; padding: 2px 0 2px 10px; }
  .blk-bridge { border-left-color: #c4463f; background: #fbeeed; }
  .blk-tab, .blk-grid, .blk-mono { border-left-color: #999; background: #f6f6f6; font-family: 'Courier New', monospace; }
  .blk-plain { border-left: 0; padding: 0; }
  .blk-l { font-size: 0.72em; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; color: #1a4f8a; margin-bottom: 3px; }
  .blk-verse .blk-l { color: #666; }
  .blk-bridge .blk-l { color: #c4463f; }
  .griffe { margin-top: 16px; border-top: 1px solid #ccc; padding-top: 10px; break-inside: avoid; }
  .griffe-t { font-weight: 700; margin-bottom: 6px; }
  .griffe-l { display: flex; flex-wrap: wrap; gap: 10px; }
  @page { margin: 16mm; }
  @media print { body { margin: 0; } }
</style></head><body>${bodyWrap}${griffHtml}</body></html>`
}

export function drucke(text, halbtoene, titel) {
  const html = chordproDoc(text, halbtoene, titel)
  const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }))
  const iframe = document.createElement('iframe')
  iframe.setAttribute('aria-hidden', 'true')
  iframe.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;'
  let aufgeraeumt = false
  const cleanup = () => {
    if (aufgeraeumt) return
    aufgeraeumt = true
    setTimeout(() => {
      iframe.remove()
      URL.revokeObjectURL(url)
    }, 500)
  }
  iframe.onload = () => {
    try {
      const cw = iframe.contentWindow
      cw.addEventListener('afterprint', cleanup)
      cw.focus()
      cw.print()
    } catch {
      cleanup()
    }
    setTimeout(cleanup, 60000) // Fallback, falls kein afterprint feuert
  }
  iframe.src = url
  document.body.appendChild(iframe)
}

function dateiname(titel, endung) {
  return ((titel || 'chordpro').replace(/[^\wäöüÄÖÜß\- ]+/g, '').trim().replace(/\s+/g, '_') || 'chordpro') + endung
}

// Rohtext (ChordPro-Quelle) speichern — wieder importierbar
export function speichereDatei(text, titel) {
  const blob = new Blob([text || ''], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = dateiname(titel || titelAus(text), '.chordpro')
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export async function sende(text, titel) {
  const t = titel || titelAus(text) || 'Noten'
  if (navigator.share) {
    try {
      await navigator.share({ title: t, text: text || '' })
      return
    } catch {
      return // vom Nutzer abgebrochen
    }
  }
  window.location.href =
    'mailto:?subject=' + encodeURIComponent(t) + '&body=' + encodeURIComponent(text || '')
}
