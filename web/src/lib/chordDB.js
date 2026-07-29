// Gängige Gitarrengriffe (Standardstimmung, Open-Position) — recherchiert.
// frets: 6 Werte E-A-D-G-H-e; -1 = x (nicht gespielt), 0 = leer, sonst Bundnummer.
const DB = {
  "C": { frets: [-1, 3, 2, 0, 1, 0], base: 1 },
  "D": { frets: [-1, -1, 0, 2, 3, 2], base: 1 },
  "E": { frets: [0, 2, 2, 1, 0, 0], base: 1 },
  "F": { frets: [1, 3, 3, 2, 1, 1], base: 1 },
  "G": { frets: [3, 2, 0, 0, 0, 3], base: 1 },
  "A": { frets: [-1, 0, 2, 2, 2, 0], base: 1 },
  "B": { frets: [-1, 2, 4, 4, 4, 2], base: 1 },
  "Am": { frets: [-1, 0, 2, 2, 1, 0], base: 1 },
  "Bm": { frets: [-1, 2, 4, 4, 3, 2], base: 1 },
  "Cm": { frets: [-1, 3, 5, 5, 4, 3], base: 1 },
  "Dm": { frets: [-1, -1, 0, 2, 3, 1], base: 1 },
  "Em": { frets: [0, 2, 2, 0, 0, 0], base: 1 },
  "Fm": { frets: [1, 3, 3, 1, 1, 1], base: 1 },
  "Gm": { frets: [3, 5, 5, 3, 3, 3], base: 1 },
  "C7": { frets: [-1, 3, 2, 3, 1, 0], base: 1 },
  "D7": { frets: [-1, -1, 0, 2, 1, 2], base: 1 },
  "E7": { frets: [0, 2, 0, 1, 0, 0], base: 1 },
  "G7": { frets: [3, 2, 0, 0, 0, 1], base: 1 },
  "A7": { frets: [-1, 0, 2, 0, 2, 0], base: 1 },
  "B7": { frets: [-1, 2, 1, 2, 0, 2], base: 1 },
  "H7": { frets: [-1, 2, 1, 2, 0, 2], base: 1 },
  "Cmaj7": { frets: [-1, 3, 2, 0, 0, 0], base: 1 },
  "Dm7": { frets: [-1, -1, 0, 2, 1, 1], base: 1 },
  "Em7": { frets: [0, 2, 0, 0, 0, 0], base: 1 },
  "Am7": { frets: [-1, 0, 2, 0, 1, 0], base: 1 },
  "Dsus4": { frets: [-1, -1, 0, 2, 3, 3], base: 1 },
  "Asus2": { frets: [-1, 0, 2, 2, 0, 0], base: 1 },
  "F#m": { frets: [2, 4, 4, 2, 2, 2], base: 1 },
  "Bb": { frets: [-1, 1, 3, 3, 3, 1], base: 1 },
  "Fmaj7": { frets: [-1, -1, 3, 2, 1, 0], base: 1 },
  "Gmaj7": { frets: [3, 2, 0, 0, 0, 2], base: 1 },
  "Amaj7": { frets: [-1, 0, 2, 1, 2, 0], base: 1 },
  "Dmaj7": { frets: [-1, -1, 0, 2, 2, 2], base: 1 },
  "Emaj7": { frets: [0, 2, 1, 1, 0, 0], base: 1 },
  "Esus4": { frets: [0, 2, 2, 2, 0, 0], base: 1 },
  "Asus4": { frets: [-1, 0, 2, 2, 3, 0], base: 1 },
  "Cadd9": { frets: [-1, 3, 2, 0, 3, 0], base: 1 },
  "Bm7": { frets: [-1, 2, 0, 2, 0, 2], base: 1 },
  "F#m7": { frets: [2, 4, 2, 2, 2, 2], base: 1 },
  "Bb7": { frets: [-1, 1, 3, 1, 3, 1], base: 1 },
}

const ENH = { Db: 'C#', 'D#': 'Eb', Gb: 'F#', 'G#': 'Ab', 'A#': 'Bb', 'C#': 'Db', Eb: 'D#', 'F#': 'Gb', Ab: 'G#', Bb: 'A#' }

// Griffbild zu einem Akkordnamen finden (ohne Bass-Zusatz), sonst null.
export function griff(name) {
  if (!name) return null
  let n = String(name).split('/')[0].trim()
  if (DB[n]) return { name: n, ...DB[n] }
  // Grundton enharmonisch tauschen und Suffix behalten
  const m = n.match(/^([A-G][#b]?)(.*)$/)
  if (m && ENH[m[1]]) {
    const alt = ENH[m[1]] + m[2]
    if (DB[alt]) return { name: n, ...DB[alt] }
  }
  return null
}

export function alleGriffe() { return DB }

