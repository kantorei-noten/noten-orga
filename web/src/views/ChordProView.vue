<script setup>
import { ref } from 'vue'

import ChordProEditor from '@/components/ChordProEditor.vue'
import ChordProSheet from '@/components/ChordProSheet.vue'
import { erkenneTonart, transponiereAkkord } from '@/lib/chordpro'
import { drucke, sende, speichereDatei, titelAus } from '@/lib/chordproExport'
import { computed } from 'vue'

const eingabe = ref(
  '{title: Amazing Grace}\n{key: G}\n\n' +
    '{start_of_verse}\n' +
    '[G]Amazing [G7]grace, how [C]sweet the [G]sound\n' +
    'That [G]saved a [D]wretch like [G]me\n' +
    '{end_of_verse}\n\n' +
    '{start_of_chorus}\n' +
    '[C]Praise [G]God, [D]praise [G]God\n' +
    '{end_of_chorus}'
)
const halbtoene = ref(0)

const tonart = computed(() => erkenneTonart(eingabe.value))
const aktuelleTonart = computed(() =>
  tonart.value ? transponiereAkkord(tonart.value.label, ((halbtoene.value % 12) + 12) % 12) : null
)
const exportTitel = computed(() => titelAus(eingabe.value) || 'ChordPro')
</script>

<template>
  <h1>ChordPro — Text &amp; Akkorde</h1>
  <p class="hilfe muted">
    ChordPro schreibt <b>Akkorde in eckigen Klammern direkt in den Text</b> — genau vor der Silbe, auf der der
    Akkord gespielt wird, z.&nbsp;B. <code>[G]Amazing [C]grace</code>. Du musst die Syntax nicht tippen:
    nutze die <b>Token</b> über dem Eingabefeld (anklicken oder hineinziehen); Akkorde und Angaben werden
    im Text <b>farbig hervorgehoben</b>. Rechts erscheint der Text mit den <b>Akkorden über den Silben</b>.
    Mit <b>Halbtöne −/+</b> transponierst du alle Akkorde auf einmal (z.&nbsp;B. für eine andere Stimmlage).
    Das Ergebnis kannst du <b>drucken, speichern oder versenden</b>.
  </p>

  <div class="toolbar">
    <span class="muted">Halbtöne</span>
    <button class="btn sm secondary" @click="halbtoene = Math.max(-11, halbtoene - 1)">−</button>
    <b style="min-width: 60px; text-align: center; font-variant-numeric: tabular-nums">
      {{ halbtoene > 0 ? '+' : '' }}{{ halbtoene }}
    </b>
    <button class="btn sm secondary" @click="halbtoene = Math.min(11, halbtoene + 1)">+</button>
    <button class="btn sm ghost" @click="halbtoene = 0">0</button>
    <span v-if="tonart" class="muted" style="margin-left: 12px">
      Tonart<template v-if="!tonart.angegeben"> (vermutlich)</template>: <b>{{ tonart.label }}</b>
      <template v-if="halbtoene !== 0"> → <b>{{ aktuelleTonart }}</b></template>
    </span>
    <span style="flex: 1" />
    <button class="btn sm secondary" @click="drucke(eingabe, halbtoene, exportTitel)">Drucken</button>
    <button class="btn sm ghost" @click="speichereDatei(eingabe, exportTitel)">Speichern</button>
    <button class="btn sm ghost" @click="sende(eingabe, exportTitel)">Senden</button>
  </div>

  <div class="cp-grid">
    <ChordProEditor v-model="eingabe" />
    <div class="cp out"><ChordProSheet :text="eingabe" :halbtoene="halbtoene" /></div>
  </div>
</template>

<style scoped>
.hilfe { max-width: 70ch; margin: -4px 0 14px; line-height: 1.5; }
.hilfe code { background: var(--surface); border: 1px solid var(--border); border-radius: 5px; padding: 0 4px; font-size: 0.9em; }
.cp-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.cp { min-height: 340px; }
textarea.cp { font-family: var(--font-mono); font-size: 13px; white-space: pre; }
.out { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 14px; overflow: auto; margin: 0; }
@media (max-width: 640px) { .cp-grid { grid-template-columns: 1fr; } }
</style>
