<script setup>
import { transponiereAkkord } from '@/lib/chordpro'

const props = defineProps({
  z: { type: Object, required: true },
  halbtoene: { type: Number, default: 0 }
})

const META = {
  key: 'Tonart',
  capo: 'Kapodaster',
  tempo: 'Tempo',
  time: 'Taktart',
  duration: 'Dauer',
  artist: 'Interpret',
  composer: 'Komponist',
  lyricist: 'Text',
  copyright: '©',
  album: 'Album',
  year: 'Jahr',
  tag: 'Schlagwort'
}

function metaWert(z) {
  const n = (((props.halbtoene % 12) + 12) % 12)
  if (z.name === 'key') return transponiereAkkord(z.wert, n)
  if (z.name === 'tempo') return /\d/.test(z.wert) ? z.wert + ' BPM' : z.wert
  return z.wert
}
// {meta: name value}
function metaGeneric(z) {
  const w = z.wert || ''
  const i = w.indexOf(' ')
  return i < 0 ? { k: w, v: '' } : { k: w.slice(0, i), v: w.slice(i + 1) }
}
</script>

<template>
  <h3 v-if="z.typ === 'direktive' && (z.name === 'title' || z.name === 't')" class="cp-title">{{ z.wert }}</h3>
  <p v-else-if="z.typ === 'direktive' && (z.name === 'subtitle' || z.name === 'st')" class="cp-sub">{{ z.wert }}</p>
  <p v-else-if="z.typ === 'direktive' && META[z.name]" class="cp-meta">
    <span class="cp-meta-l">{{ META[z.name] }}:</span> {{ metaWert(z) }}
  </p>
  <p v-else-if="z.typ === 'direktive' && z.name === 'meta'" class="cp-meta">
    <span class="cp-meta-l">{{ metaGeneric(z).k }}:</span> {{ metaGeneric(z).v }}
  </p>
  <p v-else-if="z.typ === 'direktive' && (z.name === 'comment_box' || z.name === 'cb')" class="cp-cbox">{{ z.wert }}</p>
  <p v-else-if="z.typ === 'direktive' && z.name === 'highlight'" class="cp-highlight">{{ z.wert }}</p>
  <p v-else-if="z.typ === 'direktive' && (z.name === 'comment_italic' || z.name === 'ci')" class="cp-comment cp-italic">{{ z.wert }}</p>
  <p v-else-if="z.typ === 'direktive' && (z.name === 'comment' || z.name === 'c')" class="cp-comment">{{ z.wert }}</p>
  <p v-else-if="z.typ === 'ref'" class="cp-ref">↻ {{ z.label }}</p>
  <p v-else-if="z.typ === 'direktive'" class="cp-comment cp-italic">{{ z.wert || z.name }}</p>
  <div v-else-if="z.typ === 'leer'" class="cp-leer" />
  <div v-else class="cp-line">
    <template v-for="(col, j) in z.cols" :key="j">
      <span v-if="col.marke" class="cp-marke">{{ col.marke }}</span>
      <span v-else class="cp-col">
        <span class="cp-ch" :class="{ 'cp-ann': !col.akkord && col.annotation }">{{ col.akkord || col.annotation }}</span>
        <span class="cp-ly">{{ col.text }}</span>
      </span>
    </template>
  </div>
</template>

<style scoped>
.cp-title { margin: 0 0 2px; font-size: 18px; }
.cp-sub { margin: 0 0 8px; color: var(--ink-2); }
.cp-meta { margin: 1px 0; color: var(--ink-2); font-size: 0.9em; }
.cp-meta-l { color: var(--ink); font-weight: 600; }
.cp-comment { margin: 4px 0; color: var(--ink-2); background: var(--surface); border-radius: 5px; padding: 2px 8px; display: inline-block; }
.cp-italic { font-style: italic; }
.cp-cbox { margin: 4px 0; padding: 3px 9px; border: 1px solid var(--border-strong); border-radius: 6px; display: inline-block; }
.cp-highlight { margin: 4px 0; padding: 3px 9px; border-radius: 6px; display: inline-block; background: var(--accent-tint); color: var(--accent-strong); font-weight: 600; }
.cp-ref { margin: 4px 0; color: var(--accent-strong); font-weight: 600; }
.cp-leer { height: 12px; }
.cp-line { display: flex; flex-wrap: wrap; align-items: flex-end; margin: 2px 0; }
.cp-col { display: inline-flex; flex-direction: column; justify-content: flex-end; }
.cp-ch { color: var(--accent-strong); font-weight: 700; font-size: 0.82em; height: 1.35em; line-height: 1.35em; white-space: pre; }
.cp-ch.cp-ann { color: var(--ink-2); font-weight: 400; font-style: italic; }
.cp-ly { white-space: pre; }
.cp-marke { align-self: center; margin: 0 6px; padding: 1px 8px; border-radius: var(--radius-pill); background: var(--accent-tint); color: var(--accent-strong); font-size: 0.8em; font-weight: 600; }
</style>
