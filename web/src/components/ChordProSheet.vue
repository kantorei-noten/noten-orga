<script setup>
import { computed, ref } from 'vue'

import { akkordeImText, parseDefines, parseZeile, songTranspose, transponiere } from '@/lib/chordpro'
import { griff } from '@/lib/chordDB'
import ChordDiagram from './ChordDiagram.vue'
import ChordProZeile from './ChordProZeile.vue'

const props = defineProps({
  text: { type: String, default: '' },
  halbtoene: { type: Number, default: 0 }
})

const BLOCK_START = {
  start_of_chorus: 'chorus', soc: 'chorus',
  start_of_verse: 'verse', sov: 'verse',
  start_of_bridge: 'bridge', sob: 'bridge',
  start_of_tab: 'tab', sot: 'tab',
  start_of_grid: 'grid', sog: 'grid',
  start_of_abc: 'abc', start_of_ly: 'ly', start_of_svg: 'svg', start_of_textblock: 'text'
}
const BLOCK_END = new Set([
  'end_of_chorus', 'eoc', 'end_of_verse', 'eov', 'end_of_bridge', 'eob',
  'end_of_tab', 'eot', 'end_of_grid', 'eog', 'end_of_abc', 'end_of_ly', 'end_of_svg', 'end_of_textblock'
])
const BLOCK_LABEL = { chorus: 'Refrain', verse: 'Strophe', bridge: 'Bridge', tab: 'Tabulatur', grid: 'Grid', abc: 'ABC-Notation', ly: 'LilyPond', svg: 'SVG', text: '' }
const MONO = new Set(['tab', 'grid', 'abc', 'ly', 'svg'])
// Reine Ausgabe-/Layout-/Font-/Sortier-Direktiven → im Web ignorieren (nicht als Text zeigen)
const IGNORE = new Set([
  'new_song', 'ns', 'sorttitle', 'sortartist', 'image', 'pagetype', 'titles', 'grid', 'g', 'no_grid', 'ng',
  'columns', 'col', 'column_break', 'colb', 'new_page', 'np', 'new_physical_page', 'npp',
  'diagrams', 'define', 'chord', 'transpose',
  'textfont', 'tf', 'textsize', 'ts', 'textcolour', 'chordfont', 'cf', 'chordsize', 'cs', 'chordcolour',
  'chorusfont', 'chorussize', 'choruscolour', 'tabfont', 'tabsize', 'tabcolour', 'gridfont', 'gridsize', 'gridcolour',
  'titlefont', 'titlesize', 'titlecolour', 'footerfont', 'footersize', 'footercolour',
  'labelfont', 'labelsize', 'labelcolour', 'tocfont', 'tocsize', 'toccolour'
])

const effN = computed(() => props.halbtoene + songTranspose(props.text || ''))

const doc = computed(() => {
  const zeilen = transponiere(props.text || '', effN.value).split('\n').map(parseZeile)
  const items = []
  let block = null
  let strophe = 0
  const push = (it) => (block ? block.kinder : items).push(it)
  for (const z of zeilen) {
    if (z.typ === 'ignoriert') continue
    if (z.typ === 'direktive') {
      if (BLOCK_START[z.name] !== undefined) {
        if (block) items.push(block)
        const typ = BLOCK_START[z.name]
        let label = z.wert
        if (typ === 'verse') {
          strophe += 1
          if (!label) label = 'Strophe ' + strophe
        } else if (!label) {
          label = BLOCK_LABEL[typ]
        }
        block = { block: true, typ, label, mono: MONO.has(typ), kinder: [] }
        continue
      }
      if (BLOCK_END.has(z.name)) {
        if (block) {
          items.push(block)
          block = null
        }
        continue
      }
      if (z.name === 'chorus') {
        push({ typ: 'ref', label: z.wert || 'Refrain' })
        continue
      }
      if (IGNORE.has(z.name)) continue
    }
    push(z)
  }
  if (block) items.push(block)
  return items
})

// --- Griffbilder ---
const diagrammeAn = ref(true)
const griffe = computed(() => {
  const t = props.text || ''
  if (/\{\s*(no_grid|ng)\s*\}/i.test(t)) return []
  const d = t.match(/\{\s*diagrams\s*:\s*([^}]*)\}/i)
  if (d && /^(none|off|no)/i.test((d[1] || '').trim())) return []
  const defs = parseDefines(t)
  const namen = akkordeImText(transponiere(t, effN.value))
  const out = []
  const seen = new Set()
  for (const nm of namen) {
    if (seen.has(nm)) continue
    seen.add(nm)
    if (defs[nm]) out.push({ name: nm, frets: defs[nm].frets, base: defs[nm].base })
    else {
      const g = griff(nm)
      if (g) out.push({ name: nm, frets: g.frets, base: g.base })
    }
  }
  for (const k in defs) {
    if (!seen.has(k)) {
      out.push({ name: k, frets: defs[k].frets, base: defs[k].base })
      seen.add(k)
    }
  }
  return out
})
</script>

<template>
  <div class="sheet">
    <template v-for="(it, i) in doc" :key="i">
      <section v-if="it.block" class="cp-block" :class="['cp-' + it.typ, { mono: it.mono }]">
        <div v-if="it.label" class="cp-block-label">{{ it.label }}</div>
        <ChordProZeile v-for="(z, j) in it.kinder" :key="j" :z="z" :halbtoene="effN" />
      </section>
      <ChordProZeile v-else :z="it" :halbtoene="effN" />
    </template>

    <div v-if="griffe.length" class="cp-griffe">
      <div class="cp-griffe-kopf">
        <b>Griffbilder</b>
        <button class="cp-toggle" @click="diagrammeAn = !diagrammeAn">{{ diagrammeAn ? 'ausblenden' : 'anzeigen' }}</button>
      </div>
      <div v-if="diagrammeAn" class="cp-griffe-liste">
        <ChordDiagram v-for="g in griffe" :key="g.name" :name="g.name" :frets="g.frets" :base="g.base" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.sheet { font-size: 15px; line-height: 1.35; color: var(--ink); }
.cp-block { margin: 8px 0; padding: 6px 12px; border-left: 3px solid var(--accent); background: var(--accent-tint); border-radius: 0 6px 6px 0; }
.cp-block.cp-verse { border-left-color: var(--border-strong); background: transparent; padding: 2px 0 2px 12px; }
.cp-block.cp-bridge { border-left-color: #c4463f; background: rgba(196, 70, 63, 0.06); }
.cp-block.mono { border-left-color: var(--ink-2); background: var(--surface); font-family: var(--font-mono); font-size: 0.92em; white-space: pre-wrap; }
.cp-block-label { font-size: 0.72em; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; color: var(--accent-strong); margin-bottom: 3px; }
.cp-block.cp-verse .cp-block-label { color: var(--ink-2); }
.cp-block.cp-bridge .cp-block-label { color: #c4463f; }
.cp-block.mono .cp-block-label { color: var(--ink-2); }
.cp-griffe { margin-top: 16px; border-top: 1px solid var(--border); padding-top: 10px; }
.cp-griffe-kopf { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.cp-toggle { border: none; background: none; color: var(--accent); font: inherit; font-size: 12px; cursor: pointer; padding: 0; }
.cp-griffe-liste { display: flex; flex-wrap: wrap; gap: 10px; }
</style>
