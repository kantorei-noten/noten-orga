// Druckansicht des Dienstplans: Termine mit Teilnehmer-Zusagen + Gruppen-Roster.
// Rein clientseitig, gedruckt über ein verstecktes iframe (wie chordproExport).

const ART = { chor: 'Chor', blaeser: 'Bläser', band: 'Band', sonstige: 'Sonstige' }

function esc(s) {
  return String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c])
}
function datumLang(iso) {
  if (!iso) return 'ohne Datum'
  try {
    return new Date(iso + 'T12:00:00').toLocaleDateString('de-DE', {
      weekday: 'long',
      day: '2-digit',
      month: 'long',
      year: 'numeric'
    })
  } catch {
    return iso
  }
}
function statusText(s) {
  return s === 'zugesagt' ? 'zugesagt ✓' : s === 'abgesagt' ? 'abgesagt ✕' : 'offen'
}

function baueHtml(dienste, gruppen) {
  const termine = [...(dienste || [])].sort((a, b) => (a.datum || '9999').localeCompare(b.datum || '9999'))
  const heute = new Date().toLocaleDateString('de-DE')

  const termineHtml =
    termine
      .map((d) => {
        const t = d.teilnehmer || []
        const ja = t.filter((x) => x.status === 'zugesagt').length
        const nein = t.filter((x) => x.status === 'abgesagt').length
        const offen = t.length - ja - nein
        const rows =
          t
            .map(
              (x) =>
                `<tr><td>${esc(x.benutzername)}</td><td class="st ${x.status}">${statusText(x.status)}</td><td>${esc(x.notiz || '')}</td></tr>`
            )
            .join('') || '<tr><td colspan="3" class="muted">Keine Mitglieder in der Gruppe</td></tr>'
        return `<section class="termin">
        <h2>${datumLang(d.datum)} — ${esc(d.gruppe_name)}${d.bestaetigt ? ' <span class="bt">✓ bestätigt</span>' : ''}</h2>
        <div class="meta">${d.setliste_name ? `Setliste: <b>${esc(d.setliste_name)}</b> · ` : ''}Zusagen: <b>${ja}</b> · Absagen: <b>${nein}</b> · offen: <b>${offen}</b>${d.notiz ? `<br>Notiz: ${esc(d.notiz)}` : ''}</div>
        <table><thead><tr><th>Mitglied</th><th>Status</th><th>Notiz</th></tr></thead><tbody>${rows}</tbody></table>
      </section>`
      })
      .join('') || '<p class="muted">Keine Termine.</p>'

  const gruppenHtml =
    (gruppen || [])
      .map((g) => {
        const m = (g.mitglieder || []).map((x) => esc(x.benutzername)).join(', ') || '—'
        return `<div class="grow"><b>${esc(g.name)}</b> <span class="art">(${ART[g.art] || esc(g.art)})</span>: ${m}</div>`
      })
      .join('') || '<p class="muted">Keine Gruppen.</p>'

  return `<!doctype html><html lang="de"><head><meta charset="utf-8"><title>Dienstplan</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: -apple-system, Helvetica, Arial, sans-serif; color: #111; margin: 24px; font-size: 12px; }
    h1 { font-size: 20px; margin: 0; }
    .gen { color: #666; font-size: 11px; margin: 2px 0 16px; }
    .termin { margin: 0 0 14px; page-break-inside: avoid; }
    .termin h2 { font-size: 14px; margin: 0 0 3px; border-bottom: 1px solid #ccc; padding-bottom: 2px; }
    .bt { color: #2e7d32; font-size: 11px; }
    .meta { color: #333; margin: 0 0 4px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; border: 1px solid #ddd; padding: 3px 6px; vertical-align: top; }
    th { background: #f3f3f3; }
    .st.zugesagt { color: #2e7d32; font-weight: 600; }
    .st.abgesagt { color: #c0392b; font-weight: 600; }
    .muted { color: #888; }
    .gruppen { margin-top: 20px; }
    .gruppen h2 { font-size: 14px; border-bottom: 1px solid #ccc; padding-bottom: 2px; }
    .grow { margin: 3px 0; }
    .art { color: #666; }
    @media print { body { margin: 12mm; } }
  </style></head><body>
  <header><h1>Dienstplan</h1><div class="gen">Stand: ${heute}</div></header>
  ${termineHtml}
  <section class="gruppen"><h2>Gruppen &amp; Mitglieder</h2>${gruppenHtml}</section>
  <footer style="margin-top:24px;color:#888;font-size:10px;text-align:center;border-top:1px solid #eee;padding-top:8px">© 2026 by Michael Henseleit · Kantorei-Notenarchiv</footer>
  </body></html>`
}

export function druckeDienstplan(dienste, gruppen) {
  const url = URL.createObjectURL(new Blob([baueHtml(dienste, gruppen)], { type: 'text/html' }))
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
    setTimeout(cleanup, 60000)
  }
  iframe.src = url
  document.body.appendChild(iframe)
}
