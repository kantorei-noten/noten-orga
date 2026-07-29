<script setup>
import { computed, nextTick, ref } from 'vue'

import { istAkkord } from '@/lib/chordpro'

const props = defineProps({
  modelValue: { type: String, default: '' }
})
const emit = defineEmits(['update:modelValue'])
const ta = ref(null)
const hl = ref(null)
const fileInput = ref(null)

// ‸ = Cursor-Position nach dem Einfügen (nur beim Klick; beim Ziehen wird der klare Text genommen)
const angaben = [
  { label: 'Titel', klick: '{title: ‸}\n', zieh: '{title: }\n' },
  { label: 'Untertitel', klick: '{subtitle: ‸}\n', zieh: '{subtitle: }\n' },
  { label: 'Kommentar', klick: '{comment: ‸}\n', zieh: '{comment: }\n' },
  { label: 'Tonart', klick: '{key: ‸}\n', zieh: '{key: }\n' },
  { label: 'Kapo', klick: '{capo: ‸}\n', zieh: '{capo: }\n' },
  { label: 'Tempo', klick: '{tempo: ‸}\n', zieh: '{tempo: }\n' },
  { label: 'Refrain', klick: '{start_of_chorus}\n‸\n{end_of_chorus}\n', zieh: '{start_of_chorus}\n\n{end_of_chorus}\n' },
  { label: 'Strophe', klick: '{start_of_verse}\n‸\n{end_of_verse}\n', zieh: '{start_of_verse}\n\n{end_of_verse}\n' },
  { label: 'Bridge', klick: '{start_of_bridge}\n‸\n{end_of_bridge}\n', zieh: '{start_of_bridge}\n\n{end_of_bridge}\n' }
]
const akkorde = [
  'C', 'D', 'E', 'F', 'G', 'A', 'B',
  'Am', 'Dm', 'Em', 'Gm', 'Bm', 'F#m',
  'C7', 'D7', 'E7', 'G7', 'A7', 'Cmaj7', 'Dsus4'
]

function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
// Farbige Hervorhebung als Backdrop hinter dem transparenten Textfeld
const highlighted = computed(() => {
  const s = props.modelValue || ''
  const re = /(\{[^}]*\})|(\[[^\]]*\])/g
  let out = ''
  let last = 0
  let m
  while ((m = re.exec(s))) {
    out += esc(s.slice(last, m.index))
    if (m[1]) {
      out += '<span class="cp-dir">' + esc(m[1]) + '</span>'
    } else {
      const inner = m[2].slice(1, -1)
      out += '<span class="' + (istAkkord(inner) ? 'cp-chord' : 'cp-mark') + '">' + esc(m[2]) + '</span>'
    }
    last = re.lastIndex
  }
  out += esc(s.slice(last))
  return out + '\n' // Zeilenumbruch am Ende, damit Backdrop-Höhe zur Textarea passt
})

function setModel(text, caret) {
  emit('update:modelValue', text)
  nextTick(() => {
    const el = ta.value
    if (!el) return
    el.focus()
    el.selectionStart = el.selectionEnd = caret
    syncScroll()
  })
}
function einfuegen(snippet) {
  const el = ta.value
  const val = props.modelValue || ''
  const start = el ? el.selectionStart : val.length
  const end = el ? el.selectionEnd : val.length
  const marker = snippet.indexOf('‸')
  const clean = snippet.replace('‸', '')
  const neu = val.slice(0, start) + clean + val.slice(end)
  const caret = marker >= 0 ? start + marker : start + clean.length
  setModel(neu, caret)
}
function akkordEinfuegen(ch) {
  einfuegen('[' + ch + ']')
}
function onDrag(ev, text) {
  ev.dataTransfer.setData('text/plain', text)
  ev.dataTransfer.effectAllowed = 'copy'
}
function oeffneDatei() {
  fileInput.value?.click()
}
function dateiGewaehlt(ev) {
  const f = ev.target.files && ev.target.files[0]
  if (!f) return
  const reader = new FileReader()
  reader.onload = () => emit('update:modelValue', String(reader.result || ''))
  reader.readAsText(f)
  ev.target.value = '' // gleiche Datei erneut wählbar
}
function onInput(ev) {
  emit('update:modelValue', ev.target.value)
  nextTick(syncScroll)
}
function syncScroll() {
  if (hl.value && ta.value) {
    hl.value.scrollTop = ta.value.scrollTop
    hl.value.scrollLeft = ta.value.scrollLeft
  }
}
</script>

<template>
  <div class="cpe">
    <div class="palette">
      <span class="grp">Angaben</span>
      <button
        v-for="a in angaben"
        :key="a.label"
        class="tok"
        draggable="true"
        :title="'Einfügen: ' + a.zieh.trim()"
        @click="einfuegen(a.klick)"
        @dragstart="onDrag($event, a.zieh)"
      >{{ a.label }}</button>
      <button class="tok datei" title="ChordPro-Datei importieren (.chordpro/.cho/.txt)" @click="oeffneDatei">📂 Öffnen …</button>
      <input
        ref="fileInput"
        type="file"
        accept=".chordpro,.cho,.crd,.pro,.txt,text/plain"
        style="display: none"
        @change="dateiGewaehlt"
      />
    </div>
    <div class="palette">
      <span class="grp">Akkorde</span>
      <button
        v-for="c in akkorde"
        :key="c"
        class="tok chord"
        draggable="true"
        :title="'[' + c + ']'"
        @click="akkordEinfuegen(c)"
        @dragstart="onDrag($event, '[' + c + ']')"
      >{{ c }}</button>
    </div>

    <div class="cpwrap">
      <pre ref="hl" class="hl" aria-hidden="true" v-html="highlighted" />
      <textarea
        ref="ta"
        class="cp-ta"
        :value="modelValue"
        spellcheck="false"
        placeholder="{title: …}&#10;[G]Amazing [C]grace, how [G]sweet the [D]sound"
        @input="onInput"
        @scroll="syncScroll"
      />
    </div>

    <p class="tip muted">
      Token <b>anklicken</b> (fügt an der Cursor-Stelle ein) oder <b>in den Text ziehen</b> —
      <span class="cp-chord">Akkorde</span> und <span class="cp-dir">Angaben</span> werden im Text farbig hervorgehoben.
    </p>
  </div>
</template>

<style scoped>
.cpe { display: flex; flex-direction: column; gap: 6px; }
.palette { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.grp { font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-2); margin-right: 2px; min-width: 58px; }
.tok {
  border: 1px solid var(--border-strong);
  background: var(--paper);
  color: var(--ink);
  border-radius: var(--radius-pill);
  padding: 3px 10px;
  font-size: 12px;
  cursor: grab;
  user-select: none;
}
.tok:hover { border-color: var(--accent); background: var(--accent-tint); }
.tok:active { cursor: grabbing; }
.tok.chord { font-weight: 700; color: var(--accent-strong); font-variant-numeric: tabular-nums; }

/* Textfeld mit farbiger Backdrop-Ebene (gleiche Metrik → deckungsgleich) */
.cpwrap {
  position: relative;
  margin-top: 2px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--paper);
  min-height: 240px;
}
.cpwrap:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-tint); }
.hl,
.cp-ta {
  margin: 0;
  padding: 10px 12px;
  border: 0;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  box-sizing: border-box;
  width: 100%;
}
.hl {
  position: absolute;
  inset: 0;
  overflow: auto;
  pointer-events: none;
  color: var(--ink);
}
.cp-ta {
  position: relative;
  display: block;
  min-height: 240px;
  background: transparent;
  color: transparent;
  caret-color: var(--ink);
  resize: vertical;
  outline: none;
}
.cp-ta::placeholder { color: var(--ink-2); }
:deep(.cp-chord) { color: var(--accent-strong); font-weight: 700; }
:deep(.cp-dir) { color: #2E9E5B; font-style: italic; }
:deep(.cp-mark) { color: #C4463F; font-weight: 700; }
.tip { font-size: 12px; margin: 2px 0 0; }
.tip .cp-chord { color: var(--accent-strong); font-weight: 700; }
.tip .cp-dir { color: #2E9E5B; font-style: italic; }
</style>
