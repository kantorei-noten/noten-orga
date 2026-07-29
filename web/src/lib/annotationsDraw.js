// Annotationen (Striche + Text-Notizen) auf einen 2D-Canvas-Context zeichnen.
// Koordinaten sind normalisiert 0..1000; w/h = Canvas-Pixelmaße.
const FARBE = { fingersatz: '#2E6EB5', registrierung: '#2E9E5B', notiz: '#C4463F' }

export function zeichneAnnotationen(ctx, w, h, rows) {
  for (const row of rows || []) {
    const col = FARBE[row.ebene] || '#333'
    const d = row.daten || {}
    const strokes = d.strokes || (d.paths || []).map((p) => ({ punkte: p }))

    ctx.strokeStyle = col
    ctx.lineWidth = Math.max(1.5, (4 / 1000) * w)
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    for (const s of strokes) {
      const pts = s.punkte || []
      if (!pts.length) continue
      ctx.beginPath()
      ctx.moveTo((pts[0][0] / 1000) * w, (pts[0][1] / 1000) * h)
      for (let i = 1; i < pts.length; i++) ctx.lineTo((pts[i][0] / 1000) * w, (pts[i][1] / 1000) * h)
      ctx.stroke()
    }

    for (const t of d.texts || []) {
      const fpx = Math.max(11, ((t.size || 16) / 1000) * w * 1.35)
      ctx.font = '600 ' + fpx + "px system-ui, -apple-system, 'Segoe UI', sans-serif"
      ctx.textBaseline = 'top'
      const x = (t.x / 1000) * w
      const y = (t.y / 1000) * h
      // weißer Rand → über den Noten lesbar
      ctx.lineJoin = 'round'
      ctx.lineWidth = fpx * 0.22
      ctx.strokeStyle = 'rgba(255,255,255,0.92)'
      ctx.strokeText(t.text || '', x, y)
      ctx.fillStyle = col
      ctx.fillText(t.text || '', x, y)
    }
  }
}
