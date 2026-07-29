// ChordPro: Transponieren, Tonart-Erkennung und Parsen für die Anzeige.
// Portiert aus app/chordpro.py (gleiche Logik) — clientseitig für sofortige Vorschau.

const SCALE = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
const INDEX = {
  C: 0, 'C#': 1, Db: 1, D: 2, 'D#': 3, Eb: 3, E: 4, Fb: 4, 'E#': 5,
  F: 5, 'F#': 6, Gb: 6, G: 7, 'G#': 8, Ab: 8, A: 9, 'A#': 10, Bb: 10,
  B: 11, Cb: 11, 'B#': 0
}
const CHORD_RE = /^[A-G][#b]?(?:(?:[mM]|maj|min|dim|aug|sus|add|[0-9°+])[0-9A-Za-z#b()+\-]*)?(?:\/[A-G][#b]?)?$/

function shift(note, n) {
  return note in INDEX ? SCALE[(INDEX[note] + n) % 12] : note
}

export function istAkkord(token) {
  return CHORD_RE.test(token)
}

export function transponiereAkkord(token, n) {
  if (!CHORD_RE.test(token)) return token
  let bass = null
  let body = token
  const si = body.lastIndexOf('/')
  if (si > 0) {
    bass = body.slice(si + 1)
    body = body.slice(0, si)
  }
  const m = body.match(/^([A-G][#b]?)(.*)$/)
  if (!m) return token
  let res = shift(m[1], n) + m[2]
  if (bass !== null) res += '/' + shift(bass, n)
  return res
}

export function transponiere(text, halbtoene) {
  const n = (((halbtoene % 12) + 12) % 12)
  if (n === 0) return text
  return text.replace(/\[([^\]]+)\]/g, (_, c) => '[' + transponiereAkkord(c, n) + ']')
}

// Tonart: bevorzugt die explizite {key: …}-Angabe, sonst Schätzung aus den Akkorden.
export function erkenneTonart(text) {
  const k = (text || '').match(/\{\s*key\s*:\s*([A-G][#b]?)(m|min)?\b[^}]*\}/i)
  if (k) {
    const grundton = k[1]
    const moll = !!k[2]
    return { grundton, moll, label: grundton + (moll ? 'm' : ''), angegeben: true }
  }
  const chords = []
  ;(text || '').replace(/\[([^\]]+)\]/g, (_, c) => {
    if (CHORD_RE.test(c)) chords.push(c)
    return _
  })
  if (!chords.length) return null
  const rootOf = (ch) => {
    const b = ch.split('/')[0]
    const m = b.match(/^([A-G][#b]?)(.*)$/)
    return m ? { root: m[1], rest: m[2] } : null
  }
  const pick = rootOf(chords[chords.length - 1]) || rootOf(chords[0])
  if (!pick) return null
  const moll = /^m(?!aj)/.test(pick.rest)
  return { grundton: pick.root, moll, label: pick.root + (moll ? 'm' : ''), angegeben: false }
}

// Eine Zeile in Direktive / leere Zeile / Kommentar / Spalten (Akkord über Text) zerlegen.
export function parseZeile(zeile) {
  if (!zeile.trim()) return { typ: 'leer' }
  if (/^\s*#/.test(zeile)) return { typ: 'ignoriert' } // #-Kommentarzeile (nicht anzeigen)
  const dir = zeile.match(/^\s*\{([^}]*)\}\s*$/)
  if (dir) {
    const p = dir[1].split(':')
    return { typ: 'direktive', name: (p[0] || '').trim().toLowerCase(), wert: p.slice(1).join(':').trim() }
  }
  const re = /\[([^\]]+)\]/g
  const cols = []
  let idx = 0
  let m
  let hatAkkord = false
  let pAkk = ''
  let pAnn = ''
  const flush = () => {
    if (pAkk || pAnn) {
      cols.push({ akkord: pAkk, annotation: pAnn, text: '' })
      pAkk = ''
      pAnn = ''
    }
  }
  while ((m = re.exec(zeile))) {
    const vor = zeile.slice(idx, m.index)
    if (vor) {
      cols.push({ akkord: pAkk, annotation: pAnn, text: vor })
      pAkk = ''
      pAnn = ''
    }
    const inhalt = m[1]
    if (inhalt.startsWith('*')) {
      flush()
      pAnn = inhalt.slice(1) // [*Text] = textuelle Annotation, kein Akkord
    } else if (istAkkord(inhalt)) {
      flush()
      pAkk = inhalt
      hatAkkord = true
    } else {
      flush()
      cols.push({ marke: inhalt })
    }
    idx = re.lastIndex
  }
  const rest = zeile.slice(idx)
  if (rest || pAkk || pAnn) cols.push({ akkord: pAkk, annotation: pAnn, text: rest })
  return { typ: 'zeile', cols, hatAkkord }
}

// Summe aller {transpose: N}-Direktiven (Song-Offset).
export function songTranspose(text) {
  let s = 0
  ;(text || '').replace(/\{\s*transpose\s*:\s*(-?\d+)\s*\}/gi, (_, nn) => {
    s += parseInt(nn, 10) || 0
    return _
  })
  return s
}

// Distinkte echte Akkorde im Text (für Griffbilder), ohne Bass-Zusatz.
export function akkordeImText(text) {
  const seen = new Set()
  const liste = []
  ;(text || '').replace(/\[([^\]]+)\]/g, (_, c) => {
    if (!c.startsWith('*') && istAkkord(c)) {
      const base = c.split('/')[0]
      if (!seen.has(base)) {
        seen.add(base)
        liste.push(base)
      }
    }
    return _
  })
  return liste
}

// Eigene Akkord-Definitionen: {define: NAME base-fret N frets a b c d e f ...}
export function parseDefines(text) {
  const defs = {}
  const re = /\{\s*(?:define|chord)\s*:\s*([^}]*)\}/gi
  let m
  while ((m = re.exec(text || ''))) {
    const s = m[1]
    const name = (s.match(/^\s*(\S+)/) || [])[1]
    if (!name) continue
    const fr = s.match(/frets\s+([\dxXnN\s-]+?)(?:\s+fingers|\s*$)/i)
    if (!fr) continue
    let frets = fr[1].trim().split(/\s+/).map((t) => (/^\d+$/.test(t) ? parseInt(t, 10) : -1))
    while (frets.length < 6) frets.push(-1)
    frets = frets.slice(0, 6)
    const bf = s.match(/base-fret\s+(\d+)/i)
    defs[name] = { name, frets, base: bf ? parseInt(bf[1], 10) : 1 }
  }
  return defs
}
